from charts.chart_widget import HistoryChart

class OIChart(HistoryChart):
    def __init__(self):
        super().__init__("Open Interest", "#26A69A")
