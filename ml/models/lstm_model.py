"""LSTM with attention model for SoundPulse prediction engine.

Processes sequences of daily feature vectors (14-day lookback) through
an LSTM with an attention mechanism that weights recent days more heavily.

PyTorch-based. Gracefully degrades if torch is not installed.
"""

import logging
import pickle
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.utils.data import DataLoader, TensorDataset

    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    logger.warning("PyTorch not installed. LSTM model will be unavailable.")


if TORCH_AVAILABLE:

    class Attention(nn.Module):
        """Additive attention over LSTM hidden states."""

        def __init__(self, hidden_size: int):
            super().__init__()
            self.attention = nn.Sequential(
                nn.Linear(hidden_size, hidden_size),
                nn.Tanh(),
                nn.Linear(hidden_size, 1),
            )

        def forward(self, lstm_output: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
            """
            Args:
                lstm_output: (batch, seq_len, hidden_size)
            Returns:
                context: (batch, hidden_size)
                weights: (batch, seq_len)
            """
            attn_weights = self.attention(lstm_output).squeeze(-1)  # (batch, seq_len)
            attn_weights = torch.softmax(attn_weights, dim=1)
            context = torch.bmm(attn_weights.unsqueeze(1), lstm_output).squeeze(1)
            return context, attn_weights

    class LSTMAttentionNet(nn.Module):
        """LSTM -> Attention -> Dense -> Sigmoid."""

        def __init__(
            self,
            input_size: int,
            hidden_size: int = 64,
            num_layers: int = 2,
            dropout: float = 0.3,
        ):
            super().__init__()
            self.lstm = nn.LSTM(
                input_size=input_size,
                hidden_size=hidden_size,
                num_layers=num_layers,
                batch_first=True,
                dropout=dropout if num_layers > 1 else 0.0,
                bidirectional=False,
            )
            self.attention = Attention(hidden_size)
            self.classifier = nn.Sequential(
                nn.Linear(hidden_size, 32),
                nn.ReLU(),
                nn.Dropout(dropout),
                nn.Linear(32, 1),
                nn.Sigmoid(),
            )

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            """
            Args:
                x: (batch, seq_len, input_size)
            Returns:
                prob: (batch,) probability of positive class
            """
            lstm_out, _ = self.lstm(x)  # (batch, seq_len, hidden)
            context, _ = self.attention(lstm_out)  # (batch, hidden)
            return self.classifier(context).squeeze(-1)  # (batch,)


class LSTMModel:
    """LSTM with attention wrapper for the SoundPulse ensemble.

    Input: sequences of shape (n_samples, seq_len, n_features).
    """

    name = "lstm"

    def __init__(
        self,
        input_size: int | None = None,
        seq_len: int = 14,
        hidden_size: int = 64,
        num_layers: int = 2,
        dropout: float = 0.3,
        lr: float = 1e-3,
        epochs: int = 50,
        batch_size: int = 64,
    ):
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch is required but not installed.")

        self.input_size = input_size
        self.seq_len = seq_len
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.dropout = dropout
        self.lr = lr
        self.epochs = epochs
        self.batch_size = batch_size
        self.model: Any = None
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    def _build_model(self, input_size: int) -> "LSTMAttentionNet":
        net = LSTMAttentionNet(
            input_size=input_size,
            hidden_size=self.hidden_size,
            num_layers=self.num_layers,
            dropout=self.dropout,
        )
        return net.to(self.device)

    def train(
        self,
        sequences: np.ndarray,
        labels: np.ndarray,
        val_sequences: np.ndarray | None = None,
        val_labels: np.ndarray | None = None,
    ) -> dict[str, float]:
        """Train the LSTM model on sequences.

        Args:
            sequences: shape (n_samples, seq_len, n_features)
            labels: shape (n_samples,) binary labels
            val_sequences: optional validation sequences
            val_labels: optional validation labels

        Returns:
            dict of training metrics.
        """
        self.input_size = sequences.shape[2]
        self.model = self._build_model(self.input_size)

        X_tensor = torch.FloatTensor(sequences).to(self.device)
        y_tensor = torch.FloatTensor(labels).to(self.device)
        dataset = TensorDataset(X_tensor, y_tensor)
        loader = DataLoader(dataset, batch_size=self.batch_size, shuffle=True)

        optimizer = optim.Adam(self.model.parameters(), lr=self.lr, weight_decay=1e-5)
        scheduler = optim.lr_scheduler.ReduceLROnPlateau(
            optimizer, mode="min", factor=0.5, patience=5
        )
        criterion = nn.BCELoss()

        best_val_loss = float("inf")
        best_state = None
        patience_counter = 0
        patience = 10

        for epoch in range(self.epochs):
            self.model.train()
            epoch_loss = 0.0
            for X_batch, y_batch in loader:
                optimizer.zero_grad()
                pred = self.model(X_batch)
                loss = criterion(pred, y_batch)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
                optimizer.step()
                epoch_loss += loss.item() * len(X_batch)

            epoch_loss /= len(dataset)

            # Validation
            val_loss = epoch_loss
            if val_sequences is not None and val_labels is not None:
                self.model.eval()
                with torch.no_grad():
                    val_X = torch.FloatTensor(val_sequences).to(self.device)
                    val_y = torch.FloatTensor(val_labels).to(self.device)
                    val_pred = self.model(val_X)
                    val_loss = criterion(val_pred, val_y).item()

            scheduler.step(val_loss)

            if val_loss < best_val_loss:
                best_val_loss = val_loss
                best_state = {k: v.cpu().clone() for k, v in self.model.state_dict().items()}
                patience_counter = 0
            else:
                patience_counter += 1

            if patience_counter >= patience:
                logger.info("Early stopping at epoch %d", epoch + 1)
                break

            if (epoch + 1) % 10 == 0:
                logger.info(
                    "Epoch %d/%d — train_loss: %.4f, val_loss: %.4f",
                    epoch + 1,
                    self.epochs,
                    epoch_loss,
                    val_loss,
                )

        # Restore best weights
        if best_state is not None:
            self.model.load_state_dict(best_state)

        logger.info("LSTM training complete. Best val loss: %.4f", best_val_loss)
        return {"best_val_loss": best_val_loss, "epochs_trained": epoch + 1}

    def predict(self, sequences: np.ndarray) -> np.ndarray:
        """Return probability of positive class for each sequence.

        Args:
            sequences: shape (n_samples, seq_len, n_features)
        Returns:
            probabilities: shape (n_samples,)
        """
        if self.model is None:
            raise RuntimeError("Model not trained. Call train() first.")

        self.model.eval()
        with torch.no_grad():
            X_tensor = torch.FloatTensor(sequences).to(self.device)
            probs = self.model(X_tensor).cpu().numpy()
        return probs

    def save(self, path: str | Path) -> None:
        """Save model to disk."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "state_dict": self.model.state_dict() if self.model else None,
            "input_size": self.input_size,
            "seq_len": self.seq_len,
            "hidden_size": self.hidden_size,
            "num_layers": self.num_layers,
            "dropout": self.dropout,
        }
        with open(path, "wb") as f:
            pickle.dump(data, f)
        logger.info("LSTM model saved to %s", path)

    def load(self, path: str | Path) -> None:
        """Load model from disk."""
        path = Path(path)
        with open(path, "rb") as f:
            data = pickle.load(f)

        self.input_size = data["input_size"]
        self.seq_len = data.get("seq_len", 14)
        self.hidden_size = data.get("hidden_size", 64)
        self.num_layers = data.get("num_layers", 2)
        self.dropout = data.get("dropout", 0.3)

        if data["state_dict"] is not None and self.input_size is not None:
            self.model = self._build_model(self.input_size)
            self.model.load_state_dict(data["state_dict"])
            self.model.eval()
            logger.info("LSTM model loaded from %s", path)
        else:
            logger.warning("No state_dict found in %s", path)

    @property
    def is_trained(self) -> bool:
        return self.model is not None
