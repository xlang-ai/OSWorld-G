import sys
import json
import os
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QHBoxLayout, 
                            QTreeWidget, QTreeWidgetItem, QLabel, QPushButton,
                            QVBoxLayout, QComboBox)
from PyQt5.QtGui import QPixmap, QPainter, QPen
from PyQt5.QtCore import Qt, QRect

class LayoutViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.current_file_index = 0
        self.file_pairs = []  # 存储图片和JSON文件对
        self.initUI()
        
    def initUI(self):
        self.setWindowTitle('Layout Viewer')
        self.setGeometry(100, 100, 1200, 800)
        
        # 修改主布局为垂直布局
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        vbox = QVBoxLayout()
        main_widget.setLayout(vbox)
        
        # 添加文件夹选择下拉菜单
        self.folder_combo = QComboBox()
        # 动态获取文件夹列表
        folders = self.get_data_folders()
        self.folder_combo.addItems(folders)
        self.folder_combo.currentTextChanged.connect(self.onFolderChanged)
        vbox.addWidget(self.folder_combo)
        
        # 添加水平布局用于放置内容
        content_widget = QWidget()
        hbox = QHBoxLayout()
        content_widget.setLayout(hbox)
        
        # 创建树形控件和图片标签 (保持原有代码)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabel('Layout Hierarchy')
        self.tree.itemClicked.connect(self.onTreeItemClicked)
        hbox.addWidget(self.tree)
        
        # 创建右侧垂直布局，包含图片和按钮
        right_layout = QVBoxLayout()
        
        # 添加导航按钮
        nav_layout = QHBoxLayout()
        self.prev_button = QPushButton('Previous')
        self.next_button = QPushButton('Next')
        self.prev_button.clicked.connect(self.show_previous)
        self.next_button.clicked.connect(self.show_next)
        nav_layout.addWidget(self.prev_button)
        nav_layout.addWidget(self.next_button)
        
        # 添加文件名显示标签
        self.file_label = QLabel()
        self.file_label.setAlignment(Qt.AlignCenter)
        right_layout.addLayout(nav_layout)
        right_layout.addWidget(self.file_label)
        
        # 创建图片标签
        self.image_label = QLabel()
        self.image_label.setMinimumSize(800, 600)
        self.max_display_size = (800, 600)  # 设置最大显示尺寸
        self.image_label.setAlignment(Qt.AlignCenter)
        right_layout.addWidget(self.image_label)
        
        hbox.addLayout(right_layout)
        vbox.addWidget(content_widget)
        
        self.current_bbox = None
        
    def onFolderChanged(self, folder_name):
        """当选择的文件夹改变时触发"""
        folder_path = os.path.join('./data', folder_name)
        self.loadFolder(folder_path)

    def loadFolder(self, folder_path):
        """加载文件夹中的所有图片和对应的JSON文件"""
        self.file_pairs = []
        if not os.path.exists(folder_path):
            print(f"Folder not found: {folder_path}")
            return
            
        for file in os.listdir(folder_path):
            if file.endswith('.png'):
                json_file = os.path.splitext(file)[0] + '.json'
                if os.path.exists(os.path.join(folder_path, json_file)):
                    self.file_pairs.append({
                        'image': os.path.join(folder_path, file),
                        'json': os.path.join(folder_path, json_file)
                    })
        
        if self.file_pairs:
            self.current_file_index = 0
            self.load_current_file()
        else:
            # 清空显示
            self.image_label.clear()
            self.tree.clear()
            self.file_label.setText("No files found")
            
    def load_current_file(self):
        """加载当前索引对应的文件对"""
        if 0 <= self.current_file_index < len(self.file_pairs):
            # 清除当前的边界框
            self.current_bbox = None
            
            current_pair = self.file_pairs[self.current_file_index]
            self.loadImage(current_pair['image'])
            self.loadHierarchy(current_pair['json'])
            self.file_label.setText(os.path.basename(current_pair['image']))
            
    def show_previous(self):
        """显示上一个文件对"""
        if self.current_file_index > 0:
            self.current_file_index -= 1
            self.load_current_file()
            
    def show_next(self):
        """显示下一个文件对"""
        if self.current_file_index < len(self.file_pairs) - 1:
            self.current_file_index += 1
            self.load_current_file()
        
    def loadImage(self, image_path):
        self.original_pixmap = QPixmap(image_path)
        self.scale_factor = self.calculateScaleFactor(self.original_pixmap.size())
        self.updateImage()
        
    def calculateScaleFactor(self, image_size):
        """计算图像需要的缩放比例"""
        max_w, max_h = self.max_display_size
        img_w, img_h = image_size.width(), image_size.height()
        
        # 如果图像尺寸在限制范围内，则不缩放
        if img_w <= max_w and img_h <= max_h:
            return 1.0
            
        # 计算宽度和高度的缩放比例，选择较小的以保证完整显示
        w_scale = max_w / img_w
        h_scale = max_h / img_h
        return min(w_scale, h_scale)
        
    def loadHierarchy(self, json_path):
        # 清除现有的树形结构
        self.tree.clear()
        
        with open(json_path, 'r') as f:
            hierarchy = json.load(f)
        # 保存根节点坐标用于转换
        self.root_x = float(hierarchy.get('x', 0))
        self.root_y = float(hierarchy.get('y', 0))
        self.buildTree(hierarchy)
        
    def buildTree(self, data, parent=None):
        if parent is None:
            item = QTreeWidgetItem(self.tree)
        else:
            item = QTreeWidgetItem(parent)
            
        name = data.get('name', 'Unknown')
        item.setText(0, name)
        # 保存原始坐标信息，不进行缩放
        info = {
            'x': float(data.get('x', 0)) - self.root_x,
            'y': float(data.get('y', 0)) - self.root_y,
            'width': float(data.get('width', 0)),
            'height': float(data.get('height', 0)),
            'name': name,
            'type': data.get('type', 'Unknown')
        }
        item.setData(0, Qt.UserRole, info)
        
        if 'children' in data:
            for child in data['children']:
                self.buildTree(child, item)
                
    def onTreeItemClicked(self, item, column):
        self.current_bbox = item.data(0, Qt.UserRole)
        self.updateImage()
        
    def updateImage(self):
        if not hasattr(self, 'original_pixmap'):
            return
            
        # 创建缩放后的pixmap，确保使用整数
        scaled_pixmap = self.original_pixmap.scaled(
            int(self.original_pixmap.width() * self.scale_factor),
            int(self.original_pixmap.height() * self.scale_factor),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        
        if self.current_bbox:
            painter = QPainter(scaled_pixmap)
            # 设置边界框的画笔
            pen = QPen(Qt.red, 2, Qt.SolidLine)
            painter.setPen(pen)
            
            # 使用缩放后的坐标
            x = int(self.current_bbox['x'] * self.scale_factor)
            y = int(self.current_bbox['y'] * self.scale_factor)
            w = int(self.current_bbox['width'] * self.scale_factor)
            h = int(self.current_bbox['height'] * self.scale_factor)
            
            # 绘制边界框
            painter.drawRect(x, y, w, h)

            # 设置文本的画笔颜色和字体
            painter.setPen(Qt.yellow)
            font = painter.font()
            font.setPointSize(10)
            painter.setFont(font)
            
            # 准备显示的文本
            info_text = f"Name: {self.current_bbox['name']}\nType: {self.current_bbox['type']}"
            
            # 获取文本的边界矩形
            text_rect = painter.boundingRect(QRect(), Qt.TextWordWrap, info_text)
            
            # 计算文本位置，确保在图片范围内
            text_x = x + w + 5
            text_y = y
            
            # 如果文本会超出图片右边界，就显示在边界框左侧
            if text_x + text_rect.width() > scaled_pixmap.width():
                text_x = x - text_rect.width() - 5
            
            # 如果文本会超出图片底部，就向上调整位置
            if text_y + text_rect.height() > scaled_pixmap.height():
                text_y = scaled_pixmap.height() - text_rect.height()
            
            # 如果文本位置小于0，就调整到0
            text_x = max(0, text_x)
            text_y = max(0, text_y)
            
            # 绘制文本背景
            painter.fillRect(text_x, text_y, text_rect.width(), text_rect.height(), 
                           Qt.black)
            
            # 绘制文本
            painter.drawText(text_x, text_y, text_rect.width(), text_rect.height(),
                           Qt.TextWordWrap, info_text)
            
            painter.end()
            
        self.image_label.setPixmap(scaled_pixmap)

    def get_data_folders(self):
        """获取data目录下的所有文件夹"""
        data_path = './data'
        if not os.path.exists(data_path):
            return []
        
        # 获取所有文件夹
        folders = [f for f in os.listdir(data_path) 
                  if os.path.isdir(os.path.join(data_path, f))]
        return sorted(folders)  # 按字母顺序排序

def main():
    app = QApplication(sys.argv)
    viewer = LayoutViewer()
    
    # 获取文件夹列表
    folders = viewer.get_data_folders()
    # 如果有文件夹，加载第一个
    if folders:
        viewer.loadFolder(os.path.join('./data', folders[0]))
    
    viewer.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
