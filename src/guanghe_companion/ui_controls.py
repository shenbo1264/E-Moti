from PySide6.QtCore import QRect
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QComboBox, QStyle, QStyleFactory, QStyleOption, QStyleOptionComboBox


class CompanionComboBox(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._arrow_style = QStyleFactory.create("Fusion")
        self._arrow_style.setParent(self)

    def paintEvent(self, event):
        super().paintEvent(event)
        # QSS 定义下拉槽位后不再绘制原生箭头，补回 Qt 标准图元。
        option = QStyleOptionComboBox()
        self.initStyleOption(option)
        slot = self.style().subControlRect(
            QStyle.ComplexControl.CC_ComboBox, option,
            QStyle.SubControl.SC_ComboBoxArrow, self,
        )
        arrow = QStyleOption()
        arrow.initFrom(self)
        arrow.rect = QRect(slot.center().x() - 5, slot.center().y() - 5, 11, 11)
        painter = QPainter(self)
        self._arrow_style.drawPrimitive(QStyle.PrimitiveElement.PE_IndicatorArrowDown, arrow, painter, self)
