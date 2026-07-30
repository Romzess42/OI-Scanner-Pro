from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QLineEdit,
    QPushButton,
)


class FilterBar(QWidget):
    def __init__(self):
        super().__init__()

        layout = QHBoxLayout()

        layout.addWidget(QLabel("Exchange"))

        self.exchange = QComboBox()
        self.exchange.addItems(
            [
                "Bybit",
                "Binance",
                "OKX",
                "Bitget",
            ]
        )
        layout.addWidget(self.exchange)

        layout.addWidget(QLabel("Type"))

        self.instrument = QComboBox()
        self.instrument.addItems(
            [
                "Perpetual",
                "Futures",
                "Spot",
            ]
        )
        layout.addWidget(self.instrument)

        layout.addWidget(QLabel("Timeframe"))

        self.timeframe = QComboBox()
        self.timeframe.addItems(
            [
                "15m",
                "1H",
                "4H",
                "1D",
                "1W",
                "1M",
            ]
        )
        layout.addWidget(self.timeframe)

        layout.addWidget(QLabel("Search"))

        self.search = QLineEdit()
        self.search.setPlaceholderText("BTCUSDT...")
        layout.addWidget(self.search)

        self.refresh = QPushButton("Refresh")

        layout.addWidget(self.refresh)

        layout.addStretch()

        self.setLayout(layout)