from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QBrush, QPen, QFont, QPolygon
from PyQt6.QtCore import Qt, QPoint


class IconHelper:
    """图标辅助类，用于创建自定义图标"""
    
    @staticmethod
    def create_colored_icon(color, size=16):
        """创建纯色圆形图标"""
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 绘制圆形
        painter.setBrush(QBrush(QColor(color)))
        painter.setPen(QPen(Qt.PenStyle.NoPen))
        painter.drawEllipse(2, 2, size-4, size-4)
        
        painter.end()
        return QIcon(pixmap)
    
    @staticmethod
    def create_text_icon(text, color="#FFFFFF", bg_color="#0078D4", size=16):
        """创建文字图标"""
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 绘制背景圆形
        painter.setBrush(QBrush(QColor(bg_color)))
        painter.setPen(QPen(Qt.PenStyle.NoPen))
        painter.drawEllipse(0, 0, size, size)
        
        # 绘制文字
        painter.setPen(QPen(QColor(color)))
        font = QFont("Arial", max(6, size//3), QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(0, 0, size, size, Qt.AlignmentFlag.AlignCenter, text)
        
        painter.end()
        return QIcon(pixmap)
    
    @staticmethod
    def create_arrow_icon(direction="right", color="#FFFFFF", size=16):
        """创建箭头图标"""
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        painter.setBrush(QBrush(QColor(color)))
        painter.setPen(QPen(Qt.PenStyle.NoPen))
        
        # 绘制三角形箭头
        if direction == "right":
            points = [
                (size//4, size//4),
                (3*size//4, size//2),
                (size//4, 3*size//4)
            ]
        elif direction == "down":
            points = [
                (size//4, size//4),
                (size//2, 3*size//4),
                (3*size//4, size//4)
            ]
        else:
            points = [
                (size//4, size//2),
                (3*size//4, size//4),
                (3*size//4, 3*size//4)
            ]
        
        from PyQt6.QtCore import QPoint
        polygon = QPolygon()
        for x, y in points:
            polygon.append(QPoint(x, y))
        painter.drawPolygon(polygon)
        
        painter.end()
        return QIcon(pixmap)
    
    @staticmethod
    def create_file_icon(color="#4A90E2", size=16):
        """创建文件图标"""
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 绘制文件形状
        painter.setBrush(QBrush(QColor(color)))
        painter.setPen(QPen(QColor("#2C3E50"), 1))
        
        # 文件主体
        painter.drawRect(2, 4, size-6, size-6)
        
        # 文件折角
        painter.setBrush(QBrush(QColor("#FFFFFF")))
        polygon = QPolygon()
        polygon.append(QPoint(size-6, 4))
        polygon.append(QPoint(size-2, 4))
        polygon.append(QPoint(size-2, 8))
        polygon.append(QPoint(size-6, 8))
        painter.drawPolygon(polygon)
        
        painter.end()
        return QIcon(pixmap)
    
    @staticmethod
    def create_chart_icon(color="#28A745", size=16):
        """创建图表图标"""
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        painter.setPen(QPen(QColor(color), 2))
        
        # 绘制简单的折线图
        points = [
            QPoint(2, size-2),
            QPoint(size//4, size//2),
            QPoint(size//2, size//4),
            QPoint(3*size//4, size//2),
            QPoint(size-2, 2)
        ]
        
        for i in range(len(points)-1):
            painter.drawLine(points[i], points[i+1])
        
        # 绘制数据点
        painter.setBrush(QBrush(QColor(color)))
        painter.setPen(QPen(Qt.PenStyle.NoPen))
        for point in points:
            painter.drawEllipse(point.x()-1, point.y()-1, 2, 2)
        
        painter.end()
        return QIcon(pixmap)
