import sys
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWebEngineWidgets import QWebEngineView
import plotly.graph_objs as go
from random import randint
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import io

from tools import fill_missing_bins, generate_right_skewed_dist, generate_left_skewed_dist, \
    merge_and_filter_intervals, calculate_decile, calculate_mean, calculate_median, \
    calculate_mode, calculate_min, calculate_max, calculate_quartiles, generate_sample_data, calculate_percentile, \
    get_interval_boundaries, calculate_stdev, sort_intervals, valid_data_ranges


def latex_to_pixmap(latex, dpi=100):

    def colorize_pixmap(image):
        colored_image = QImage(image.size(), QImage.Format_ARGB32)
        colored_image.fill(Qt.transparent)

        painter = QPainter(colored_image)
        painter.setCompositionMode(QPainter.CompositionMode_Source)
        painter.drawImage(0, 0, image)
        painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
        painter.fillRect(colored_image.rect(), QColor('white'))
        painter.end()

        return QPixmap.fromImage(colored_image)

    fig, ax = plt.subplots(figsize=(1, 1))
    ax.text(0.5, 0.5, f'${latex}$', horizontalalignment='center', verticalalignment='center', fontsize=15)
    ax.axis('off')
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=dpi, bbox_inches='tight', pad_inches=0, transparent=True)
    plt.close(fig)
    buf.seek(0)

    # Load image from buffer
    image = QImage()
    image.loadFromData(buf.getvalue())

    image = colorize_pixmap(image)
    return image


class SpreadMeasuresWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.init_main_table()
        self.init_main_table_toolbar()
        self.init_output_table()
        self.exporter = FileExporter(self)

        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search...")  # Placeholder text
        self.search_bar.textChanged.connect(self.search_output_table)

        layout = QVBoxLayout()
        self.setLayout(layout)

        main_widget = QWidget()
        main_table_layout = QVBoxLayout()
        main_table_layout.addWidget(self.main_table_toolbar)
        main_table_layout.addWidget(self.main_table)
        main_widget.setLayout(main_table_layout)

        output_widget = QWidget()
        output_layout = QVBoxLayout()
        output_layout.addWidget(self.search_bar)
        output_layout.addWidget(self.output_table)
        output_widget.setLayout(output_layout)

        self.stack_layout = QStackedLayout()
        self.stack_layout.addWidget(main_widget)
        self.stack_layout.addWidget(output_widget)

        # Create a QComboBox for navigation
        self.combobox_pages = QComboBox()
        for item in ['Frequency table', 'Output table']:
            self.combobox_pages.addItem(item)

        # Connect comboBox index change to a method that updates the visible widget
        self.combobox_pages.currentIndexChanged.connect(self.displayPage)

        layout.addWidget(self.combobox_pages)
        layout.addLayout(self.stack_layout)

    def displayPage(self, index):
        self.stack_layout.setCurrentIndex(index)

    def init_main_table(self):
        self.main_table = QTableWidget()
        self.main_table.setSelectionBehavior(QAbstractItemView.SelectRows)

    def search_output_table(self):
        searchText = self.search_bar.text().lower()

        for row in range(self.output_table.rowCount()):
            item = self.output_table.item(row, 0)  # Search only in the first column
            if item and searchText in item.text().lower():
                self.output_table.setRowHidden(row, False)  # Show matching row
            else:
                self.output_table.setRowHidden(row, True)  # Hide non-matching row

    def create_action(self, icon, tooltip, function):
        action = QAction(QIcon(icon), tooltip, self)

        if function:
            action.triggered.connect(function)

        if tooltip=='Export':
            menu = QMenu()

            export_csv_action = QAction('CSV File', menu)
            export_excel_action = QAction('Excel File', menu)
            export_text_action = QAction('Text File', menu)

            widget_to_export = self.main_table
            export_csv_action.triggered.connect(lambda: self.exporter.export(widget_to_export, 'csv'))
            export_excel_action.triggered.connect(lambda: self.exporter.export(widget_to_export, 'xlsx'))
            export_text_action.triggered.connect(lambda: self.exporter.export(widget_to_export, 'txt'))

            menu.addAction(export_csv_action)
            menu.addAction(export_excel_action)
            menu.addAction(export_text_action)

            action.setMenu(menu)

        return action

    def init_main_table_toolbar(self):
        self.main_table_toolbar = QToolBar()

        tooltips = ['Calculate', 'Reset table', 'Export']
        icons = [f'images/{icon}.png' for icon in
                 ['calculate','reset','export']
                 ]
        functions = [self.calculate_main_table_selections,self.update_output_table,None]
        for i in range(3):
            action = self.create_action(icons[i],tooltips[i],functions[i])
            self.main_table_toolbar.addAction(action)

    def init_output_table(self):

        self.output_table = QTableWidget()

        self.customize_update_table()

    def customize_update_table(self):

        self.mean_formula_label = QLabel()
        self.population_stdev_formula_label = QLabel()
        self.sample_stdev_formula_label = QLabel()
        self.population_var_formula_label = QLabel()
        self.sample_var_formula_label = QLabel()

        self.output_table.setColumnCount(2)
        self.output_table.setHorizontalHeaderLabels(['Statistical Property', 'Value'])
        self.output_table.setRowCount(5)

        # Set icons to specific cells
        average_label_item = QTableWidgetItem('Average =')
        average_label_item.setIcon(QIcon('images/mu.png'))

        population_stdev_label_item = QTableWidgetItem('Population Standard Deviation')
        population_stdev_label_item.setIcon(QIcon('images/stdev.png'))

        sample_stdev_label_item = QTableWidgetItem('Sample Standard Deviation')
        sample_stdev_label_item.setIcon(QIcon('images/s.png'))

        population_variance_label_item = QTableWidgetItem('Population Variance')
        population_variance_label_item.setIcon(QIcon('images/stdev_2.png'))

        sample_variance_label_item = QTableWidgetItem('Sample Variance')
        sample_variance_label_item.setIcon(QIcon('images/s_2.png'))

        # Add to table
        self.output_table.setItem(0, 0, average_label_item)
        self.output_table.setCellWidget(0, 1, self.mean_formula_label)

        self.output_table.setItem(1, 0, population_stdev_label_item)
        self.output_table.setCellWidget(1, 1, self.population_stdev_formula_label)

        self.output_table.setItem(2,0,sample_stdev_label_item)
        self.output_table.setCellWidget(2,1,self.sample_stdev_formula_label)

        self.output_table.setItem(3,0,population_variance_label_item)
        self.output_table.setCellWidget(3,1,self.population_var_formula_label)

        self.output_table.setItem(4,0,sample_variance_label_item)
        self.output_table.setCellWidget(4,1,self.sample_var_formula_label)

        for i in [0, 1]:
            self.output_table.horizontalHeader().setSectionResizeMode(i, QHeaderView.Stretch)

    def update_output_table(self, data=None):
        self.combobox_pages.setCurrentIndex(1)
        if data:
            # data from main table
            if self.est_values:
                values = [value for frequency, value in data]
                frequencies = [frequency for frequency, value in data]
            else:
                values = [value for value, frequency in data]
                frequencies = [frequency for value, frequency in data]
        else:
            # data outside
            if self.est_values:
                values = [(value[0]+value[1])/2 for value in self.values_raw]
            else:
                values = self.values_raw
            frequencies = self.frequencies_raw


        sum_valueXfreq_value = sum([value*freq for value, freq in zip(values, frequencies)])

        sum_freq_value = sum(frequencies)
        sum_freq = '{:g}'.format(sum_freq_value)

        mean_value = sum_valueXfreq_value/sum_freq_value
        mean = '{:g}'.format(mean_value)

        sum_sq_dev_value = sum(freq*((value-mean_value)**2) for value, freq in zip(values, frequencies)) #Sum of squares
        sum_sq_dev = '{:g}'.format(sum_sq_dev_value)
        population_stdev_value, population_variance_value = calculate_stdev(values,frequencies,variance=True,type='p')
        sample_stdev_value, sample_variance_value = calculate_stdev(values, frequencies, variance=True,type='s')

        self.customize_update_table()

        # Updating the mean (average) formula
        sum_valueXfreq = '{:g}'.format(sum_valueXfreq_value)
        mean_expr = f'\\frac{{{sum_valueXfreq}}}{{{sum_freq}}} = {mean}'
        pixmap = latex_to_pixmap(mean_expr)
        self.mean_formula_label.setPixmap(pixmap)
        self.mean_formula_label.setAlignment(Qt.AlignCenter)

        # Updating population standard deviation formula
        stdev = '{:g}'.format(population_stdev_value)
        stdev_expr = rf'\sqrt{{\frac{{{sum_sq_dev}}}{{{sum_freq}}}}} = {stdev}'
        pixmap = latex_to_pixmap(stdev_expr)
        self.population_stdev_formula_label.setPixmap(pixmap)
        self.population_stdev_formula_label.setAlignment(Qt.AlignCenter)

        # Updating sample standard deviation formula
        stdev = '{:g}'.format(sample_stdev_value)
        stdev_expr = rf'\sqrt{{\frac{{{sum_sq_dev}}}{{{sum_freq}-1}}}} = {stdev}'
        pixmap = latex_to_pixmap(stdev_expr)
        self.sample_stdev_formula_label.setPixmap(pixmap)
        self.sample_stdev_formula_label.setAlignment(Qt.AlignCenter)

        # Updating population variance formula
        variance = '{:g}'.format(population_variance_value)
        var_expr = rf'\frac{{{sum_sq_dev}}}{{{sum_freq}}} = {variance}'
        pixmap = latex_to_pixmap(var_expr)
        self.population_var_formula_label.setPixmap(pixmap)
        self.population_var_formula_label.setAlignment(Qt.AlignCenter)

        # Updating sample variance formula
        variance = '{:g}'.format(sample_variance_value)
        var_expr = rf'\frac{{{sum_sq_dev}}}{{{sum_freq}-1}} = {variance}'
        pixmap = latex_to_pixmap(var_expr)
        self.sample_var_formula_label.setPixmap(pixmap)
        self.sample_var_formula_label.setAlignment(Qt.AlignCenter)

        # Resize to contents
        self.output_table.resizeRowsToContents()

    def clear_all_tables(self):
        self.main_table.setRowCount(0)
        self.output_table.setRowCount(0)

        self.values_raw = None
        self.frequencies_raw = None

    def clear_all(self):
        self.clear_all_tables()

    def update_main_table(self, values, frequencies):

        self.values_raw = values
        self.frequencies_raw = frequencies

        if all(isinstance(value, tuple) for value in values):
            headers, data = self.extract_for_grouped_data()
            self.est_values = True
            self.update_output_table()
            self.populate_table(headers, data)
        else:
            headers, data = self.extract_for_ungrouped_data()
            self.est_values = False
            self.update_output_table()
            self.populate_table(headers, data)

    def calculate_main_table_selections(self):
        data = self.extract_main_table_selections()
        if self.values_raw and self.frequencies_raw:
            self.update_output_table(data)


    def extract_main_table_selections(self):
        selected_rows = set(item.row() for item in self.main_table.selectedItems())

        if self.est_values:
            data = []
            for row in selected_rows:
                if row != self.main_table.rowCount()-1: # if row is not last row
                    row = [float(self.main_table.item(row, i).text()) if i !=0 else self.main_table.item(row,i).text() for i in range(1,3)]
                    data.append(row)
        else:
            data = []
            for row in selected_rows:
                if row != self.main_table.rowCount()-1: # if row is not last row
                    row = [float(self.main_table.item(row, i).text()) for i in range(0,2)]
                    data.append(row)

        return data

    def extract_for_ungrouped_data(self):
        values, frequencies = self.values_raw, self.frequencies_raw
        headers = ['Value (x)', 'Frequency (f)', 'f × x', 'x - μ', '(x - μ)²', 'f × (x - μ)²']
        data = []

        mean_value = calculate_mean(values, frequencies)

        for i in range(len(values)):
            value = float(values[i])
            freq = int(frequencies[i])
            valueXfreq = value * freq

            value_minus_avg = value - mean_value
            value_minus_avg_sq = (value_minus_avg) ** 2
            f_value_minus_avg_sq = freq * value_minus_avg_sq

            row = []
            row.append('{:g}'.format(value))
            row.append(freq)
            row.append('{:g}'.format(valueXfreq))
            row.append('{:g}'.format(value_minus_avg))
            row.append('{:g}'.format(value_minus_avg_sq))
            row.append('{:g}'.format(f_value_minus_avg_sq))

            data.append(row)

        return headers, data

    def extract_for_grouped_data(self):
        values, frequencies = self.values_raw, self.frequencies_raw
        headers = ['Class interval', 'Frequency (f)', 'Midpoint (m)', 'f × m', 'm - μ', '(m - μ)²', 'f × (m - μ)²']
        data = []
        mean_value = calculate_mean(values, frequencies)

        for i in range(len(values)):
            midpoint = ((max(values[i])) + min(values[i])) / 2
            freq = int(frequencies[i])
            midpXfreq = midpoint * freq

            midp_minus_avg = midpoint - mean_value
            midp_minus_avg_sq = (midp_minus_avg) ** 2
            f_midp_minus_avg_sq = freq * midp_minus_avg_sq

            row = []
            row.append(f'{min(values[i])} - {max(values[i])}')
            row.append(freq)
            row.append('{:g}'.format(midpoint))
            row.append('{:g}'.format(midpXfreq))
            row.append('{:g}'.format(midp_minus_avg))
            row.append('{:g}'.format(midp_minus_avg_sq))
            row.append('{:g}'.format(f_midp_minus_avg_sq))

            data.append(row)

        return headers, data

    def populate_table(self, headers, data):
        self.main_table.setRowCount(0)

        self.main_table.setColumnCount(len(headers))
        self.main_table.setRowCount(len(data) + 1)
        self.main_table.setHorizontalHeaderLabels(headers)

        # Add data
        for row_idx, row_data in enumerate(data):
            for col_idx, item in enumerate(row_data):
                table_item = QTableWidgetItem(str(item))
                table_item.setFlags(table_item.flags() & ~Qt.ItemIsEditable)
                self.main_table.setItem(row_idx, col_idx, table_item)

        total_icon_item = QTableWidgetItem('TOTAL = ')
        total_icon_item.setIcon(QIcon("images/sigma.png"))
        self.main_table.setItem(len(data), 0, total_icon_item)

        if len(data[0]) == 7: # if grouped data
            sum_midpXfreq = sum([float(row[3]) for row in data])
            total_frequency = sum([int(row[1]) for row in data])
            sum_sq_dev = sum([float(row[-1]) for row in data])

            self.main_table.setItem(len(data), 1, QTableWidgetItem('{:g}'.format(total_frequency)))
            self.main_table.setItem(len(data), 3, QTableWidgetItem('{:g}'.format(sum_midpXfreq)))
            self.main_table.setItem(len(data), 6, QTableWidgetItem('{:g}'.format(sum_sq_dev)))
        else:
            total_frequency = sum([int(row[1]) for row in data])
            sum_valueXfreq = sum([float(row[2]) for row in data])
            sum_sq_dev = sum([float(row[-1]) for row in data])

            self.main_table.setItem(len(data), 1, QTableWidgetItem('{:g}'.format(total_frequency)))
            self.main_table.setItem(len(data), 2, QTableWidgetItem('{:g}'.format(sum_valueXfreq)))
            self.main_table.setItem(len(data), 5, QTableWidgetItem('{:g}'.format(sum_sq_dev)))

        self.main_table.setSizeAdjustPolicy(QAbstractScrollArea.AdjustToContents)
        self.main_table.resizeColumnsToContents()
        
class PositionMeasuresWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.values_raw = []
        self.frequencies_raw = []

        self.plot_cum_widget = QWebEngineView()
        self.plot_box_widget = QWebEngineView()

        self.cum_table = QTableWidget()
        self.cum_table.setColumnCount(2)
        self.cum_table.setHorizontalHeaderLabels(['Value', 'c.f.'])
        for i in range(self.cum_table.columnCount()):
            self.cum_table.horizontalHeader().setSectionResizeMode(i, QHeaderView.Stretch)

        slider_widget_layout = QVBoxLayout()
        self.percentile_slider = QSlider(Qt.Horizontal)
        self.percentile_slider.setRange(0,100)
        self.percentile_slider.sliderMoved.connect(lambda value: QToolTip.showText(QCursor.pos(), str(value), self.percentile_slider))
        self.percentile_slider.valueChanged.connect(self.update_value_for_percentile_slider)

        self.percentile_spinbox = QSpinBox()
        self.percentile_spinbox.setRange(0,100)
        self.percentile_spinbox.valueChanged.connect(lambda value: self.percentile_slider.setValue(value))
        self.percentile_spinbox.valueChanged.connect(self.update_percentile_slider_for_spinbox)

        self.percentile_value_label = QLabel()
        self.percentile_value_label.setFont(QFont('Arial',8,QFont.Bold))
        self.percentile_value_label.setAlignment(Qt.AlignRight)

        label = QLabel('Percentile: ')
        label.setFont(QFont('Arial',8,QFont.Bold))
        h_layout = QHBoxLayout()
        h_layout.setAlignment(Qt.AlignLeft)
        h_layout.addWidget(label)
        h_layout.addWidget(self.percentile_spinbox)
        slider_widget_layout.addLayout(h_layout)
        slider_widget_layout.addWidget(self.percentile_slider)
        slider_widget_layout.addWidget(self.percentile_value_label)

        slider_widget = QWidget()
        slider_widget.setLayout(slider_widget_layout)

        others_tabwidget = QTabWidget()
        others_tabwidget.tabBar().setIconSize(QSize(32, 32))
        others_tabwidget.addTab(self.plot_box_widget,'Box Plot')
        others_tabwidget.setTabIcon(0, QIcon('images/chart.png'))
        others_tabwidget.addTab(slider_widget,'Percentile Calculator')
        others_tabwidget.setTabIcon(1,QIcon('images/percentage.png'))
        others_tabwidget.addTab(self.cum_table, 'Cumulative Table')
        others_tabwidget.setTabIcon(2,QIcon('images/table.png'))

        layout = QVBoxLayout()
        layout.addWidget(self.plot_cum_widget, 65)
        layout.addWidget(others_tabwidget,35)

        self.setLayout(layout)

    def update_cum_table(self):
        values = self.values_raw
        frequencies = self.frequencies_raw
        self.cum_table.setRowCount(len(frequencies))
        cum_frequencies = np.cumsum(frequencies).tolist()
        for i in range(self.cum_table.rowCount()):
            self.cum_table.setItem(i, 0, QTableWidgetItem(
                f'≤{values[i][1]}' if all(isinstance(value, tuple) for value in values) else str(values[i])))
            self.cum_table.setItem(i, 1, QTableWidgetItem(str(cum_frequencies[i])))

    def plot(self, values, frequencies):
        self.values_raw = values
        self.frequencies_raw = frequencies
        if all(isinstance(value, tuple) for value in values):
            self.update_position_measures_widget()
        else:
            self.plot_cum_widget.setHtml('')
            self.update_box_plot()
            self.update_cum_table()
            self.update_value_for_percentile_slider()

    def update_percentile_slider_for_spinbox(self):
        self.update_value_for_percentile_slider()


    def update_value_for_percentile_slider(self, slider_value=None):
        slider_value = self.percentile_slider.value() if not slider_value else slider_value
        self.percentile_spinbox.setValue(slider_value)
        if self.values_raw and self.frequencies_raw:
            percentile_value = calculate_percentile(self.values_raw, self.frequencies_raw, slider_value)
            percentile_value = '{:g}'.format(percentile_value)

            self.percentile_value_label.setText(f'Value: {percentile_value}')
        else:
            self.percentile_value_label.setText(f'Value: None')

    def update_box_plot(self, data=None):
        data = [self.values_raw, self.frequencies_raw] if not data else data
        box_fig = go.Figure()

        if isinstance(data, list):

            data = generate_sample_data(data[0], data[1])
            df = pd.DataFrame(data, columns=['Value'])

            box_fig.add_trace(go.Box(
                x=df['Value'],
                marker_color='blue'
            ))

        elif isinstance(data, dict):
            box_fig.add_trace(go.Box(
                q1=[data['Q1']],
                median=[data['MEDIAN']],
                q3=[data['Q3']],
                lowerfence=[data['MIN']],
                upperfence=[data['MAX']],
                boxpoints=False,  # Hide all points
                marker_color='blue',
            ))

        box_fig.update_traces(orientation='h')
        box_fig.update_layout(xaxis_title='values', margin=dict(l=50, r=50, t=40, b=40), title='Box Plot')
        self.plot_box_widget.setHtml(box_fig.to_html(include_plotlyjs='cdn'))

    def clear_all(self):
        self.values_raw = None
        self.frequencies_raw = None
        self.plot_box_widget.setHtml('')
        self.plot_cum_widget.setHtml('')
        self.cum_table.setRowCount(0)
        self.update_value_for_percentile_slider()

    def update_position_measures_widget(self):
        cum_fig = go.Figure()

        # Filter data ranges to hide unnecessary bins
        data_ranges, frequencies = fill_missing_bins(self.values_raw, self.frequencies_raw)
        data_ranges, frequencies = merge_and_filter_intervals(data_ranges, frequencies)

        # Update cumulative table
        self.update_cum_table()

        # Update cumulative curve plot
        x_values = [data_range[1] for data_range in data_ranges]
        cumulative_frequencies = np.cumsum(frequencies).tolist()

        cum_fig.add_trace(go.Scatter(
            x=x_values,
            y=cumulative_frequencies,
            mode='lines+markers',
            marker_color='#FE53BB',
            name='Cumulative Frequency',
            line_shape='spline',
            hovertemplate='≤%{x:.0f} | CF = %{y:.0f}'
        ))

        # Calculate quartiles and median cumulative frequencies
        total_frequency = sum(frequencies)
        q1_y = 0.25 * (total_frequency + 1)
        median_y = 0.50 * (total_frequency + 1)
        q3_y = 0.75 * (total_frequency + 1)

        # find quartiles
        q1_x, median_x, q3_x = calculate_quartiles(data_ranges, frequencies)

        q1_x = '{:g}'.format(q1_x)
        median_x = '{:g}'.format(median_x)
        q3_x = '{:g}'.format(q3_x)

        # Add vertical lines for quartiles and median
        for x_value, y_value, label, color in zip([q1_x, median_x, q3_x], [q1_y, median_y, q3_y],
                                                  ['Lower Quartile', 'Median', 'Upper Quartile'],
                                                  ['#1ACE48', 'orange', 'red']):
            cum_fig.add_trace(go.Scatter(
                x=[x_value],
                y=[y_value],
                mode='markers',
                line=dict(color=color),
                name=label,
                marker=dict(size=8),
                hovertemplate='CF = %{y} | Quartile Value = %{x}'
            ))

        min_value = calculate_min(data_ranges, frequencies)
        max_value = calculate_max(data_ranges, frequencies)

        # Updating box and whisker plot
        self.update_box_plot({
            'Q1': q1_x,
            'MEDIAN': median_x,
            'Q3': q3_x,
            'MIN': min_value,
            'MAX': max_value
        })

        # Update percentile slider
        self.update_value_for_percentile_slider()

        # Styling the plot widget
        # Add padding to the x and y-axis ranges
        N = cumulative_frequencies[-1]
        x_min = min([data_range[0] for data_range in data_ranges]) - 5
        x_max = max([data_range[1] for data_range in data_ranges]) + 5
        y_min = -12
        y_max = N + N * 0.1

        cum_fig.update_layout(
            xaxis_title="Value",
            yaxis_title="Cumulative Frequency",
            xaxis=dict(range=[x_min, x_max], showspikes=True),
            yaxis=dict(range=[y_min, y_max], showspikes=True),
            showlegend=True,
            legend=dict(x=0, y=1.1, orientation='h'),
            margin=dict(l=50, r=50, t=40, b=40),
            plot_bgcolor='white'
        )
        # Convert to HTML and display in QWebEngineView
        self.plot_cum_widget.setHtml(cum_fig.to_html(include_plotlyjs='cdn'))

class FileExporter:
    def __init__(self, parent):
        self.parent = parent

    def get_headers(self, model):
        header_count = model.columnCount()
        headers = [model.horizontalHeaderItem(i).text() for i in range(header_count)]
        print(headers)
        return headers

    def extract_data_from_table(self, table_widget):
        data = []
        for row in range(table_widget.rowCount()):
            if not table_widget.isRowHidden(row):
                row_data = []
                for column in range(table_widget.columnCount()):
                    item = table_widget.item(row, column)
                    row_data.append(item.text() if item else '')
                data.append(row_data)
        return data

    def extract_data_from_treeview(self, model):
        data = []

        for row in range(model.rowCount()):
            property_item = model.item(row, 0)
            value_item = model.item(row, 1)
            property_text = property_item.text()
            value_text = value_item.text()
            data.append([property_text, value_text])

        return data

    def extract_data(self, model):
        if isinstance(model, QStandardItemModel):
            data = self.extract_data_from_treeview(model)
        elif isinstance(model, QTableWidget):
            data = self.extract_data_from_table(model)
        return data

    def export(self, model, file_ext):
        file_path, _ = QFileDialog.getSaveFileName(
            None, 'Export', '', f'{file_ext.upper()} Files (*.{file_ext})'
        )

        if file_path:
            if file_ext == 'txt':
                self.export_to_txt(model, file_path + '.txt' if not file_path.endswith('.txt') else file_path)
            elif file_ext == 'csv':
                self.export_to_csv(model, file_path + '.csv' if not file_path.endswith('.csv') else file_path)
            elif file_ext == 'xlsx':
                self.export_to_excel(model, file_path + '.xlsx' if not file_path.endswith('.xlsx') else file_path)
    def export_to_txt(self, model, file_path):

        data = self.extract_data(model)
        headers = self.get_headers(model)

        with open(file_path, 'w') as f:
            f.write('\t'.join(headers) + '\n')
            for row in data:
                f.write('\t'.join(map(str, row)) + '\n')

        QMessageBox.information(self.parent, "Export Successful", f"Properties exported to {file_path}")
    def export_to_csv(self, model, file_path):
        data = self.extract_data(model)
        headers = self.get_headers(model)

        df = pd.DataFrame(data, columns=headers)
        df.to_csv(file_path, index=False)

        QMessageBox.information(self.parent, "Export Successful", f"Properties exported to {file_path}")

    def export_to_excel(self, model, file_path):
        data = self.extract_data(model)
        headers = self.get_headers(model)

        df = pd.DataFrame(data, columns=headers)
        df.to_excel(file_path, index=False)

        QMessageBox.information(self.parent, "Export Successful", f"Properties exported to {file_path}")

class OutputDialog(QDialog):
    def __init__(self, title, text, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Output")

        self.layout = QVBoxLayout()
        self.title_label = QLabel(f'{title} = ')
        self.text_edit = QTextEdit()
        self.text_edit.setText(text)
        self.layout.addWidget(self.title_label)
        self.layout.addWidget(self.text_edit)

        self.setLayout(self.layout)

class OverviewWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.est_values = None
        self.exporter = FileExporter(self)

        self.plot_widget = QWebEngineView()

        self.init_properties_treeview()

        self.treeview_toolbar = QHBoxLayout()
        self.treeview_toolbar.setAlignment(Qt.AlignLeft)

        self.init_properties_searchbar()
        self.init_copy_button()
        export_treeview_button = self.create_export_button(self.tv_model)
        self.treeview_toolbar.addWidget(export_treeview_button)

        # Treeview layout
        self.treeview_layout = QVBoxLayout()
        self.treeview_layout.addWidget(self.summary_treeview)
        self.treeview_layout.addLayout(self.treeview_toolbar)
        self.treeview_tab = QWidget()
        self.treeview_tab.setLayout(self.treeview_layout)

        self.properties_tabwidget = QTabWidget()
        self.properties_tabwidget.tabBar().setIconSize(QSize(32, 32))

        self.properties_tabwidget.addTab(self.plot_widget, 'Chart')
        self.properties_tabwidget.setTabIcon(0, QIcon('images/chart.png'))

        self.properties_tabwidget.addTab(self.treeview_tab, 'Descriptive Analysis')
        self.properties_tabwidget.setTabIcon(1, QIcon("images/properties.png"))

        self.init_freq_table()
        self.properties_tabwidget.addTab(self.table_tab, 'Frequency Distribution Table')
        self.properties_tabwidget.setTabIcon(2, QIcon("images/table.png"))

        layout = QVBoxLayout()
        layout.addWidget(self.properties_tabwidget)
        self.setLayout(layout)

    def create_export_button(self, widget_to_export, tooltip='Export results', size=QSize(24, 24)):

        export_btn = QPushButton()
        export_btn.setIcon(QIcon('images/export.png'))
        export_btn.setToolTip(tooltip)
        export_btn.setIconSize(size)

        # Create menu
        menu = QMenu()

        export_csv_action = QAction('CSV File', menu)
        export_excel_action = QAction('Excel File', menu)
        export_text_action = QAction('Text File', menu)

        export_csv_action.triggered.connect(lambda: self.exporter.export(widget_to_export, 'csv'))
        export_excel_action.triggered.connect(lambda: self.exporter.export(widget_to_export, 'xlsx'))
        export_text_action.triggered.connect(lambda: self.exporter.export(widget_to_export, 'txt'))

        menu.addAction(export_csv_action)
        menu.addAction(export_excel_action)
        menu.addAction(export_text_action)

        export_btn.setMenu(menu)
        return export_btn

    def toggle_table_rows(self):
        # Check if the checkbox is checked
        hide = self.checkb_omit_zero_freq.isChecked()

        for row in range(self.freq_table.rowCount()):
            # Get the frequency value in the second column
            frequency_item = self.freq_table.item(row, 1)
            frequency = int(frequency_item.text())

            # Hide or show the row based on the frequency value
            self.freq_table.setRowHidden(row, hide and frequency == 0)

    def calculate_for_table_functions(self):
        selected_rows = set(item.row() for item in self.freq_table.selectedItems())
        current_function = self.functions_combo.currentText()

        if selected_rows:

            frequencies = [int(self.freq_table.item(row, 1).text()) for row in selected_rows]
            values_raw = [self.freq_table.item(row, 0).text() for row in selected_rows] # string format
            values = [get_interval_boundaries(raw_value) if self.est_values else float(raw_value) for raw_value in values_raw] # list and tuple format
            if current_function=='Sum':
                output_value = sum([value*freq if not self.est_values else ((value[0]+value[1])/2)*freq for value, freq in zip(values, frequencies)])
            elif current_function=='Average':
                output_value = calculate_mean(values, frequencies)
            elif current_function=='Standard Deviation':
                output_value = calculate_stdev(values, frequencies)
            elif current_function=='Variance':
                _, output_value = calculate_stdev(values, frequencies, variance=True)
            else:
                output_value = ''

            output_value = '{:g}'.format(output_value)
            dialog = OutputDialog(current_function, output_value, self)
            dialog.exec()

    def clear_all(self):
        self.clear_treeview()
        self.clear_plot()
        self.freq_table.setRowCount(0)

    def init_freq_table(self):

        self.freq_table = QTableWidget()
        self.freq_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.freq_table.setColumnCount(7)
        self.freq_table.setSelectionBehavior(QAbstractItemView.SelectRows)

        tooltips = [None,None,'Cumulative Frequency','Relative Frequency','Cumulative Relative Frequency', 'Class Width', 'Frequency Density']
        icons = [None, None, 'cumulative', 'percentage', 'percentage', None, None]
        header_text = ['Values', 'Frequencies', 'CF', 'RF', 'CRF', 'CW','FD']


        for i, (text, icon, tooltip) in enumerate(zip(header_text, icons, tooltips)):
            header_item = QTableWidgetItem(text)
            header_item.setIcon(QIcon(f'images/{icon}.png'))
            header_item.setToolTip(tooltip)

            self.freq_table.setHorizontalHeaderItem(i, header_item)

        for i in range(self.freq_table.columnCount()):
            self.freq_table.horizontalHeader().setSectionResizeMode(i, QHeaderView.Stretch)

        bottom_toolbar = QHBoxLayout()
        bottom_toolbar.setAlignment(Qt.AlignRight)

        self.checkb_omit_zero_freq = QCheckBox('Hide frequencies of zero')
        self.checkb_omit_zero_freq.setIcon(QIcon('images/remove_zero_frequencies.png'))
        self.checkb_omit_zero_freq.setIconSize(QSize(24, 24))
        self.checkb_omit_zero_freq.stateChanged.connect(self.toggle_table_rows)
        bottom_toolbar.addWidget(self.checkb_omit_zero_freq)

        table_toolbar = QHBoxLayout()
        table_toolbar.setAlignment(Qt.AlignLeft)

        self.view_headers_list_button = QPushButton()
        self.view_headers_list_button.setIcon(QIcon('images/settings.png'))
        self.view_headers_list_button.setToolTip('View frequency table headers list')
        self.view_headers_list_button.setCheckable(True)
        self.view_headers_list_button.setIconSize(QSize(24, 24))
        self.view_headers_list_button.clicked.connect(self.toggle_table_headers_list)
        table_toolbar.addWidget(self.view_headers_list_button)

        self.functions_combo = QComboBox()
        self.functions_combo.setFixedHeight(35)
        self.functions_combo.setFont(QFont('Arial', 8, QFont.Bold))
        for text in ['Sum', 'Average', 'Standard Deviation', 'Variance']:
            self.functions_combo.addItem(text)

        self.calculate_table_button = QPushButton()
        self.calculate_table_button.setIcon(QIcon('images/calculate.png'))
        self.calculate_table_button.setToolTip('Selected rows to execute the following function')
        self.calculate_table_button.setIconSize(QSize(24, 24))
        self.calculate_table_button.clicked.connect(self.calculate_for_table_functions)

        custom_combobox_functions_widget_layout = QHBoxLayout()
        custom_combobox_functions_widget_layout.setSpacing(0)
        custom_combobox_functions_widget_layout.addWidget(self.functions_combo)
        custom_combobox_functions_widget_layout.addWidget(self.calculate_table_button)
        table_toolbar.addLayout(custom_combobox_functions_widget_layout)

        self.export_table_button = self.create_export_button(self.freq_table)
        table_toolbar.addWidget(self.export_table_button)


        # TreeView for table headers
        self.freq_table_headers_view = QTreeView()
        self.freq_table_headers_view.setIndentation(0)
        self.freq_table_headers_model = QStandardItemModel()
        self.freq_table_headers_model.setHorizontalHeaderLabels(['Table Headers'])

        # Add header items to the model
        for i in range(2, self.freq_table.columnCount()):
            item = QStandardItem(f'{tooltips[i]} ({header_text[i]})')
            item.setCheckable(True)
            item.setIcon(QIcon(f'images/{icons[i]}.png' if icons else None))

            # Set the initial check state based on your criteria
            if tooltips[i] in ['Cumulative Relative Frequency', 'Relative Frequency', 'Class Width', 'Frequency Density']:  # Example condition
                item.setCheckState(Qt.Unchecked)
            else:
                item.setCheckState(Qt.Checked)

            self.freq_table_headers_model.appendRow(item)

        # Hide columns based on the initial state
        for i in range(self.freq_table_headers_model.rowCount()):
            item = self.freq_table_headers_model.item(i)
            self.on_headers_list_itemChange(item)

        self.freq_table_headers_view.setModel(self.freq_table_headers_model)
        self.freq_table_headers_view.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.freq_table_headers_view.expandAll()
        self.freq_table_headers_model.itemChanged.connect(self.on_headers_list_itemChange)

        table_tab_layout = QVBoxLayout()
        table_tab_layout.addLayout(table_toolbar)
        table_tab_layout.addWidget(self.freq_table)
        table_tab_layout.addLayout(bottom_toolbar)
        table_tab_layout.addWidget(self.freq_table_headers_view)

        self.table_tab = QWidget()
        self.table_tab.setLayout(table_tab_layout)

        self.toggle_table_headers_list()

    def toggle_table_headers_list(self):
        if self.view_headers_list_button.isChecked():
            self.freq_table_headers_view.setVisible(True)
        else:
            self.freq_table_headers_view.setVisible(False)

    def on_headers_list_itemChange(self, item):
        col_index = self.freq_table_headers_model.indexFromItem(item).row() + 2
        if item.checkState() == Qt.Checked:
            self.freq_table.setColumnHidden(col_index, False)
        else:
            self.freq_table.setColumnHidden(col_index, True)

    def update_freq_table(self):
        values = self.values_raw
        frequencies = self.frequencies_raw

        values, frequencies = fill_missing_bins(values, frequencies)
        self.freq_table.setRowCount(len(values))

        data = []
        tooltips = []
        cum_freqs = np.cumsum(frequencies).tolist()
        cum_rel_freqs = np.cumsum([freq / sum(frequencies) for freq in frequencies]).tolist()
        for i, (value, frequency) in enumerate(zip(values, frequencies)):

            class_width_value = max(value)-min(value) if self.est_values else 'null'
            freq_dens_value = '{:g}'.format(frequency/(max(value)-min(value))) if self.est_values else 'null'
            rel_freq_value = '{:g}'.format(frequency/sum(frequencies))

            # Data
            row = []
            row.append(f'{min(value)}-{max(value)}' if self.est_values else value)
            row.append(frequency)
            row.append(cum_freqs[i])
            row.append(rel_freq_value)
            row.append('{:g}'.format(cum_rel_freqs[i]))
            row.append(class_width_value)
            row.append(freq_dens_value)

            # Tooltips
            previous_freq = cum_freqs[i - 1] if i > 0 else 0
            cum_tooltip = f'{previous_freq} + {frequencies[i]} = {cum_freqs[i]}'

            relative_freq_tooltip = f'{frequency}/{sum(frequencies)}=' + rel_freq_value
            previous_cum_rel_freq = cum_rel_freqs[i - 1] if i > 0 else 0
            cum_rel_freq_tooltip = f'{previous_cum_rel_freq} + {rel_freq_value} = {cum_rel_freqs[i]}'

            class_width_tooltip = f'{max(value)} - {min(value)} = {class_width_value}' if self.est_values else None
            freq_dens_tooltip = f'{frequency} / {class_width_value} = {freq_dens_value}' if self.est_values else None
            tooltips.append([None,None,cum_tooltip,relative_freq_tooltip,cum_rel_freq_tooltip,class_width_tooltip,freq_dens_tooltip])

            data.append(row)

        for row_idx, row_data in enumerate(data):
            for col_idx, item in enumerate(row_data):
                table_item = QTableWidgetItem(str(item))
                table_item.setToolTip(tooltips[row_idx][col_idx])
                self.freq_table.setItem(row_idx, col_idx, table_item)

    def init_properties_searchbar(self):
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search...")  # Placeholder text
        self.search_bar.textChanged.connect(self.filter_treeview)
        self.treeview_toolbar.addWidget(self.search_bar)

    def init_properties_treeview(self):
        self.summary_treeview = QTreeView()
        self.summary_treeview.setIndentation(0)
        self.tv_model = self.createTreeviewModel(self)
        self.summary_treeview.setModel(self.tv_model)
        self.summary_treeview.header().setSectionResizeMode(QHeaderView.Stretch)

        self.summary_treeview.setEditTriggers(QAbstractItemView.NoEditTriggers)

    def init_copy_button(self):
        self.copy_button = QPushButton()
        self.copy_button.setIcon(QIcon('images/copy.png'))
        self.copy_button.setToolTip('Copy to clipboard')
        self.copy_button.setIconSize(QSize(24, 24))
        self.copy_button.clicked.connect(self.copy_selected_row)
        self.treeview_toolbar.addWidget(self.copy_button)

    def copy_selected_row(self):
        selected_indexes = self.summary_treeview.selectedIndexes()
        if selected_indexes:
            property_index = selected_indexes[0]
            value_index = selected_indexes[1]
            property_text = property_index.data(Qt.DisplayRole)
            value_text = value_index.data(Qt.DisplayRole)
            clipboard = QApplication.clipboard()
            clipboard.setText(f"{property_text} = {value_text}")
            QMessageBox.information(self, "Copied to Clipboard", f"Copied: {property_text} = {value_text}")

    def filter_treeview(self, text):
        if not text:
            for row in range(self.tv_model.rowCount()):
                self.summary_treeview.setRowHidden(row, QModelIndex(), False)
        else:
            text = text.lower()
            for row in range(self.tv_model.rowCount()):
                item = self.tv_model.item(row, 0)
                if text in item.text().lower():
                    self.summary_treeview.setRowHidden(row, QModelIndex(), False)
                else:
                    self.summary_treeview.setRowHidden(row, QModelIndex(), True)

    def clear_treeview(self):
        self.tv_model.removeRows(0, self.tv_model.rowCount())

    def addTreeViewProperty(self, property_, value):

        item_property = QStandardItem(property_)
        item_value = QStandardItem(str(value))

        if property_ == 'Q1':
            item_property.setIcon(QIcon('images/25_frac_icon'))
        elif property_ == 'Q2':
            item_property.setIcon(QIcon('images/50_frac_icon'))
        elif property_ == 'Q3':
            item_property.setIcon(QIcon('images/75_frac_icon'))
        elif property_ == 'Mean':
            item_property.setIcon(QIcon('images/mu.png'))
        elif property_ == 'Sample Standard Deviation':
            item_property.setIcon(QIcon('images/s.png'))
        elif property_ == 'Population Standard Deviation':
            item_property.setIcon(QIcon('images/stdev.png'))
        elif property_ == 'Sample Variance':
            item_property.setIcon(QIcon('images/s_2.png'))
        elif property_ == 'Population Variance':
            item_property.setIcon(QIcon('images/stdev_2.png'))
        elif property_ == 'Sum':
            item_property.setIcon(QIcon('images/sigma.png'))

        self.tv_model.appendRow([item_property, item_value])

    def createTreeviewModel(self, parent):
        model = QStandardItemModel(0, 2, parent)
        model.setHeaderData(0, Qt.Horizontal, 'Statistical Property')
        model.setHeaderData(1, Qt.Horizontal, 'Value')

        return model

    def update_treeview(self):

        def find_tuple_containing_value(values, target_value):
            for t in values:
                if t[0] <= target_value < t[1]:
                    return t
            return None

        values = self.values_raw
        frequencies = self.frequencies_raw

        self.clear_treeview()

        # Data Type
        data_type_bool = '(Grouped Data - Estimated Values)' if self.est_values else '(Ungrouped Data)'

        # Mean
        mean_value = calculate_mean(values, frequencies)
        mean_value = '{:g}'.format(mean_value)

        # Median
        median_value = calculate_median(values, frequencies)
        median_value = '{:g}'.format(median_value)

        if self.est_values:
            median_class = find_tuple_containing_value(values, calculate_median(values, frequencies))
            median_class = f'{min(median_class)}-{max(median_class)}'

        # Mode
        mode_value_raw = calculate_mode(values, frequencies)
        mode_value = '{' + ' , '.join(['{:g}'.format(value) for value in mode_value_raw]) + '}' + ' (multimodal)' if len(
            mode_value_raw) > 1 \
            else f'{'{:g}'.format(mode_value_raw[0])} (unimodal)'

        if self.est_values:
            if len(mode_value_raw)>1:
                modal_classes = [find_tuple_containing_value(values, mode) for mode in mode_value_raw]
                modal_classes = [f'{min(modal_class)}-{max(modal_class)}' for modal_class in modal_classes]
                modal_classes = '{' + ', '.join(modal_classes) + '}'
            else:
                modal_classes = find_tuple_containing_value(values, mode_value_raw[0])
                modal_classes = f'{min(modal_classes)}-{max(modal_classes)}'

        # Min and max
        min_value, max_value = '{:g}'.format(calculate_min(values, frequencies)), '{:g}'.format(
            calculate_max(values, frequencies))

        # Range
        range_value = '{:g}'.format(float(max_value) - float(min_value))

        # Sum of values
        sum_value = '{:g}'.format(
            sum([((value[0] + value[1]) / 2) * frequency for value, frequency in zip(values, frequencies)]) \
                if self.est_values else sum([value * frequency for value, frequency in zip(values, frequencies)]))

        # Total frequency (item count)
        total_frequency = sum(frequencies)

        # Upper and lower quartile
        q1_value, q2_value, q3_value = calculate_quartiles(values, frequencies)
        interquart_value = '{:g}'.format(q3_value - q1_value)
        q1_value = '{:g}'.format(q1_value)
        q2_value = '{:g}'.format(q2_value)
        q3_value = '{:g}'.format(q3_value)

        # standard deviation and variance
        # Population
        population_stdev_value, population_variance_value = calculate_stdev(values, frequencies, variance=True,type='p')
        population_stdev_value, population_variance_value = '{:g}'.format(population_stdev_value), '{:g}'.format(population_variance_value)
        # Sample
        sample_stdev_value, sample_variance_value = calculate_stdev(values, frequencies, variance=True,type='s')
        sample_stdev_value, sample_variance_value = '{:g}'.format(sample_stdev_value), '{:g}'.format(sample_variance_value)

        self.addTreeViewProperty('Data Type', data_type_bool)
        self.addTreeViewProperty('Mean', mean_value)

        if self.est_values:
            self.addTreeViewProperty('Modal Class', modal_classes)
        else:
            self.addTreeViewProperty('Mode', mode_value)

        if self.est_values:
            self.addTreeViewProperty('Median Class', median_class)
        else:
            self.addTreeViewProperty('Median', median_value)

        self.addTreeViewProperty('Q1', q1_value)
        self.addTreeViewProperty('Q2', q2_value)
        self.addTreeViewProperty('Q3', q3_value)
        self.addTreeViewProperty('Interquartile range', interquart_value)
        self.addTreeViewProperty('Sample Standard Deviation',sample_stdev_value)
        self.addTreeViewProperty('Sample Variance', sample_variance_value)
        self.addTreeViewProperty('Population Standard Deviation', population_stdev_value)
        self.addTreeViewProperty('Population Variance', population_variance_value)

        for decile in range(1,10):
            self.addTreeViewProperty(f'Decile {str(decile)}', '{:g}'.format(calculate_decile(values, frequencies, decile)))

        self.addTreeViewProperty('Min', min_value)
        self.addTreeViewProperty('Max', max_value)
        self.addTreeViewProperty('Range', range_value)
        self.addTreeViewProperty('Sum', sum_value)
        self.addTreeViewProperty('Total Frequency (Item count)', total_frequency)
    def plot(self, values, frequencies):

        self.values_raw = values
        self.frequencies_raw = frequencies


        if all(isinstance(value, tuple) for value in values):
            # Grouped data (data ranges) -> plot histogram

            self.est_values = True
            self.plot_histogram()

        else:
            # Ungrouped data (integer/float values) -> plot bar graph

            self.est_values = False
            self.plot_bar()

        self.update_treeview()
        self.update_freq_table()
        self.toggle_table_rows()

    def plot_bar(self):
        values = self.values_raw
        frequencies = self.frequencies_raw
        fig = go.Figure()

        fig.add_trace(go.Bar(
            x=[str(value) for value in values],
            y=frequencies,
            marker_color=frequencies,
            name='Frequency',
            hoverinfo='y+name'
        ))

        fig.update_layout(
            title='Frequency Bar Graph',
            xaxis_title="Value",
            yaxis_title="Frequency",
            showlegend=False,
            margin=dict(l=50, r=50, t=50, b=50),
            plot_bgcolor='white'
        )

        self.plot_widget.setHtml(fig.to_html(include_plotlyjs='cdn'))


    def plot_histogram(self):
        data_ranges = self.values_raw
        frequencies = self.frequencies_raw
        fig = go.Figure()

        # Handle ranges with gaps between them
        data_ranges, frequencies = fill_missing_bins(data_ranges, frequencies)

        # Initialize histogram
        bin_midpoints = [(interval[0] + interval[1]) / 2 for interval in data_ranges]
        class_widths = [interval[1] - interval[0] for interval in data_ranges]

        # Plot accordingly
        if len(set([max(interval) - min(interval) for interval, frequency in zip(data_ranges, frequencies) if
                    frequency > 0])) == 1:
            freq_density = False
        else:
            freq_density = True

        if not freq_density:
            # Normal Histogram with appropriate bar widths
            fig.add_trace(go.Bar(
                x=bin_midpoints,
                y=frequencies,
                width=class_widths,
                marker_color=frequencies,
                name='Histogram',
                hoverinfo='y+name'
            ))

            # Frequency polygon
            fig.add_trace(go.Scatter(x=[(interval[0] + interval[1]) / 2 for interval in self.values_raw], y=self.frequencies_raw, mode='lines+markers', marker_color='#47EBFF',
                                     name='Midpoint', hoverinfo='x+name'))

        else:
            # Frequency density
            frequency_densities = [frequency / width for frequency, width in zip(frequencies, class_widths)]
            fig.add_trace(go.Bar(
                x=bin_midpoints,
                y=frequency_densities,
                width=class_widths,
                marker_color=frequency_densities,
                name='Frequency Density',
                hoverinfo='y+name'
            ))

        # Finding mean, median and mode
        average_value = calculate_mean(data_ranges, frequencies)
        median_value = calculate_median(data_ranges, frequencies)
        mode_value = calculate_mode(data_ranges, frequencies)[0]

        # Add annotations for Mean, Median, and Mode as arrows
        max_y = max(frequencies)*1.05 if not freq_density else max(frequency_densities)*1.05

        for type_, value, color in zip(['Mean', 'Median', 'Mode'],[average_value, median_value, mode_value], ['red','green','blue']):
            fig.add_trace(go.Scatter(
                x=[value], y=[max_y], mode='markers',
                marker=dict(color=color, symbol='triangle-down', size=8),
                name=type_,
                hoverinfo='x+name'
            ))


        # Style the plot
        fig.update_layout(
            title="Histogram" if not freq_density else "Frequency Density",
            xaxis_title="Value",
            yaxis_title="Frequency" if not freq_density else "Frequency Density",
            showlegend=False,
            margin=dict(l=50, r=50, t=50, b=50),
            plot_bgcolor='white',
        )

        # Convert to HTML and display in QWebEngineView
        self.plot_widget.setHtml(fig.to_html(include_plotlyjs='cdn'))

    def clear_plot(self):
        self.plot_widget.setHtml("")  # Clear the plot

class InputWidget(QWidget):
    def __init__(self):
        super().__init__()

        self.exporter = FileExporter(self)

        self.main_layout = QVBoxLayout()
        self.setLayout(self.main_layout)

        self.init_interface()

    def set_select_row_mode(self, action):
        action.setIcon(QIcon('images/select_row.png'))
        self.input_table.setSelectionBehavior(QAbstractItemView.SelectRows)

    def set_select_cell_mode(self, action):
        action.setIcon(QIcon('images/select_cell.png'))
        self.input_table.setSelectionBehavior(QAbstractItemView.SelectItems)

    def create_action(self, function=None, tooltip=None, icon=None):


        action = QAction(QIcon(icon), tooltip, self)

        if function:
            action.triggered.connect(function)
        else:
            if tooltip=='Export':
                menu = QMenu()

                export_csv_action = QAction('CSV File', menu)
                export_excel_action = QAction('Excel File', menu)
                export_text_action = QAction('Text File', menu)

                widget_to_export = self.input_table
                export_csv_action.triggered.connect(lambda: self.exporter.export(widget_to_export, 'csv'))
                export_excel_action.triggered.connect(lambda: self.exporter.export(widget_to_export, 'xlsx'))
                export_text_action.triggered.connect(lambda: self.exporter.export(widget_to_export, 'txt'))

                menu.addAction(export_csv_action)
                menu.addAction(export_excel_action)
                menu.addAction(export_text_action)

                action.setMenu(menu)

            elif tooltip=='Selection mode':
                menu = QMenu()

                select_row_mode_action = QAction(icon=QIcon('images/select_row.png'), text='Row selection', parent=menu)
                select_cell_mode_action = QAction(icon=QIcon('images/select_cell.png'), text='Cell selections', parent=menu)

                select_row_mode_action.triggered.connect(lambda: self.set_select_row_mode(action))
                select_cell_mode_action.triggered.connect(lambda: self.set_select_cell_mode(action))

                menu.addAction(select_row_mode_action)
                menu.addAction(select_cell_mode_action)

                action.setMenu(menu)

                self.set_select_row_mode(action)

        return action



    def add_row(self):
        pass

    def delete_row(self):
        selected_rows = set(index.row() for index in self.input_table.selectedItems())
        for row in sorted(selected_rows, reverse=True):
            self.input_table.removeRow(row)

    def clear_cell(self):
        # Get all selected items
        selected_items = self.input_table.selectedItems()
        for item in selected_items:
            item.setText("")  # Clear the content of each selected cell


    def row_down(self):
        selected_rows = sorted(set(index.row() for index in self.input_table.selectedItems()), reverse=True)
        if selected_rows and selected_rows[
            0] == self.input_table.rowCount() - 1:  # Check if the last row is selected and prevent moving down
            return

        self.input_table.blockSignals(True)
        self.input_table.setSelectionMode(QAbstractItemView.MultiSelection)

        for row in selected_rows:
            if row < self.input_table.rowCount() - 1:
                self.input_table.insertRow(row + 2)
                for column in range(self.input_table.columnCount()):
                    self.input_table.setItem(row + 2, column,
                                                        self.input_table.takeItem(row, column))
                    self.input_table.setCurrentCell(row + 2, column)
                self.input_table.removeRow(row)

        self.input_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.input_table.blockSignals(False)

    def row_up(self):
        selected_rows = sorted(set(index.row() for index in self.input_table.selectedItems()))
        if selected_rows and selected_rows[0] == 0:  # Check if the first row is selected and prevent moving up
            return

        self.input_table.blockSignals(True)
        self.input_table.setSelectionMode(QAbstractItemView.MultiSelection)

        for row in selected_rows:
            if row > 0:
                self.input_table.insertRow(row - 1)
                for column in range(self.input_table.columnCount()):
                    self.input_table.setItem(row - 1, column,
                                                        self.input_table.takeItem(row + 1, column))
                self.input_table.removeRow(row + 1)
                self.input_table.selectRow(row - 1)

        self.input_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.input_table.blockSignals(False)

    def delete_all_rows(self):
        msg = QMessageBox.question(self, 'Confirmation', 'Remove all the rows?')
        if msg == QMessageBox.Yes:
            self.input_table.setRowCount(0)
            self.input_table.setHorizontalHeaderLabels(['Value','Frequency'])

    def clear_all_rows(self):
        msg = QMessageBox.question(self, 'Confirmation', 'Clear all input values?')
        if msg == QMessageBox.Yes:
            self.input_table.clear()
            self.input_table.setHorizontalHeaderLabels(['Value','Frequency'])

    def import_to_input_table(self):
        pass

    def update_menu_options(self):
        row_count = self.addrows_spinbox.value()
        self.add_top_action.setText(f"Add {row_count} row(s) to the top")
        self.add_bottom_action.setText(f"Add {row_count} row(s) to the bottom")

    def add_rows_top(self):
        row_count = self.addrows_spinbox.value()
        current_row = self.input_table.currentRow()
        if current_row == -1:
            current_row = 0
        for _ in range(row_count):
            self.input_table.insertRow(current_row)

    def add_rows_bottom(self):
        row_count = self.addrows_spinbox.value()
        current_row = self.input_table.currentRow()
        if current_row == -1:
            current_row = self.input_table.rowCount() - 1
        for _ in range(row_count):
            self.input_table.insertRow(current_row + 1)
            current_row += 1

    def init_addrows_spinbox(self):

        # Spinbox
        self.addrows_spinbox = QSpinBox()
        self.addrows_spinbox.setRange(1,100)
        self.addrows_spinbox.setFixedHeight(40)
        self.addrows_spinbox.valueChanged.connect(self.update_menu_options)

        add_btn = QPushButton()
        add_btn.setIcon(QIcon('images/add.png'))
        add_btn.setIconSize(QSize(24,24))
        add_btn.setToolTip('Add rows')

        menu = QMenu()

        self.add_top_action = QAction(self)
        self.add_bottom_action = QAction(self)


        self.add_top_action.triggered.connect(self.add_rows_top)
        self.add_bottom_action.triggered.connect(self.add_rows_bottom)

        menu.addAction(self.add_top_action)
        menu.addAction(self.add_bottom_action)

        add_btn.setMenu(menu)
        self.update_menu_options()

        spinbox_widget =  QWidget()
        spinbox_layout = QHBoxLayout()
        spinbox_layout.setSpacing(0)
        spinbox_layout.addWidget(self.addrows_spinbox)
        spinbox_layout.addWidget(add_btn)
        spinbox_widget.setLayout(spinbox_layout)

        self.top_toolbar.addWidget(QLabel('Add row:'))
        self.top_toolbar.addWidget(spinbox_widget)

    def init_actions_toolbar(self):
        self.top_toolbar = QToolBar()

        self.init_addrows_spinbox()

        tooltips = ['Delete row(s)','Clear row(s)','Move row down','Move row up',\
                    'Clear all rows','Remove all rows','Export','Import','Selection mode']
        icons = ['images/'+item+'.png' for item in ['delete','erase','down','up',
                                                    'clear_all','delete_all','export','import','']]
        functions = [self.delete_row, self.clear_cell, self.row_down, self.row_up,
                     self.clear_all_rows, self.delete_all_rows, None, self.import_to_input_table,None]

        for function, tooltip, icon in zip(functions,tooltips,icons):
            widget = self.create_action(function, tooltip, icon)
            if isinstance(widget,QAction):
                self.top_toolbar.addAction(widget)
            else:
                self.top_toolbar.addWidget(widget)

            if tooltip=='Clear row(s)' or tooltip=='Move row up' or tooltip=='Remove all rows'\
                    or tooltip=='Import':
                self.top_toolbar.addSeparator()

        self.main_layout.addWidget(self.top_toolbar)

    def init_input_table(self):

        self.input_table = QTableWidget()
        self.input_table.setColumnCount(2)
        self.input_table.setRowCount(20)
        for i in range(self.input_table.columnCount()):
            self.input_table.horizontalHeader().setSectionResizeMode(i, QHeaderView.Stretch)

        header_text = ['Values','Frequencies']
        description = ['Values can be grouped (class interval, like 10-20) and ungrouped (integers/floats)',\
                       'Frequencies must be positive integers']
        for i in range(self.input_table.columnCount()):
            header_item = QTableWidgetItem(header_text[i])
            header_item.setToolTip(description[i])
            self.input_table.setHorizontalHeaderItem(i, header_item)

        self.main_layout.addWidget(self.input_table)

    def init_interface(self):
        self.init_input_table()
        self.init_actions_toolbar()

class OutputWidgets:
    def __init__(self):

        self.overview_widget = OverviewWidget()
        self.position_measures_widget = PositionMeasuresWidget()
        self.spread_measures_widget = SpreadMeasuresWidget()

    def update_plots(self, data_ranges, frequencies):

        self.overview_widget.plot(data_ranges, frequencies)
        self.position_measures_widget.plot(data_ranges, frequencies)
        self.spread_measures_widget.update_main_table(data_ranges, frequencies)




class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Statistics Calculator")
        self.setWindowIcon(QIcon('images/calculate.png'))
        self.setMinimumSize(800,750)

        # Variables
        self.counter = 1

        # Main layout
        self.layout = QVBoxLayout()
        central_widget = QWidget()
        central_widget.setLayout(self.layout)
        self.setCentralWidget(central_widget)

        # Status bar
        self.init_statusbar()

        # External widgets
        self.input_widget = InputWidget()
        self.output_widget = OutputWidgets()
        self.overview_widget = self.output_widget.overview_widget
        self.position_measures_widget = self.output_widget.position_measures_widget
        self.spread_measures_widget = self.output_widget.spread_measures_widget
        self.plot_random()

        # Toolbar
        self.init_actions_toolbar()

        # Dock widgets
        self.init_dock_widgets()

        # Input widget
        self.layout.addWidget(self.input_widget)

    def tabify_dock_widgets(self, dock_widgets):
        # Ensure there are at least two dock widgets to tabify
        if len(dock_widgets) < 2:
            return

        # Tabify dock widgets
        reference_dock = dock_widgets[0]
        for dock_widget in dock_widgets[1:]:
            self.tabifyDockWidget(reference_dock, dock_widget)

    def init_dock_widgets(self):

        toolbox = QToolBox()
        toolbox.addItem(self.position_measures_widget, 'Measures of Position')
        toolbox.addItem(self.spread_measures_widget, 'Measures of Spread')
        toolbox.setItemIcon(0,QIcon('images/position.png'))
        toolbox.setItemIcon(1, QIcon('images/spread.png'))

        # Dock Widgets
        dock_widgets = []
        for title, content, dock_area in zip(['Measures of Position','Measures of spread','Overview'],
                                             [self.position_measures_widget, self.spread_measures_widget, self.overview_widget],
                                             [Qt.RightDockWidgetArea,Qt.RightDockWidgetArea,Qt.RightDockWidgetArea]):
            dock_widget = self.create_dock_widget(title,content,dock_area)
            dock_widgets.append(dock_widget)

        self.tabify_dock_widgets(dock_widgets)

    def create_dock_widget(self, title, content, dock_area):
        dock = QDockWidget(title, self)
        dock.setWidget(content)
        dock.setMinimumWidth(420)
        self.addDockWidget(dock_area, dock)
        return dock

    def init_statusbar(self):
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

    def init_actions_toolbar(self):

        self.toolbar = QToolBar()

        self.toolbar.addWidget(QLabel(' Plot: '))
        self.random_action = self.create_action('random',self.plot_random,QIcon('images/random.png'))
        self.toolbar.addAction(self.random_action)
        self.plot_action = self.create_action('Calculate inputted data',self.plot,QIcon('images/calculate.png'))
        self.toolbar.addAction(self.plot_action)

        self.toolbar.addSeparator()
        self.toolbar.addWidget(QLabel(' Clear: '))
        self.clear_plot_action = self.create_action('Clear all plots',self.clear_output_widget,QIcon('images/clear_plot.png'))
        self.toolbar.addAction(self.clear_plot_action)
        self.clear_inputs_action = self.create_action('Clear inputted data',self.input_widget.clear_all_rows,QIcon('images/clear_inputs.png'))
        self.toolbar.addAction(self.clear_inputs_action)

        self.addToolBar(self.toolbar)

    def clear_output_widget(self):

        self.output_widget.overview_widget.clear_all()
        self.output_widget.position_measures_widget.clear_all()
        self.output_widget.spread_measures_widget.clear_all()

    def plot(self):
        values_raw, frequencies_raw = self.get_data_from_input_table()
        data_ranges = get_interval_boundaries(values_raw)

        # If values are class intervals
        if len(data_ranges)>0 and all(class_str[0] is not None and class_str[1] is not None for class_str in data_ranges) and valid_data_ranges(data_ranges):
            data_ranges, frequencies = sort_intervals(data_ranges, frequencies_raw)
            self.output_widget.update_plots(data_ranges,frequencies)

            self.status_bar.showMessage('Data successfully calculated', 5000)

        # If values are integers and floats
        elif len(values_raw)>0 and all(isinstance(value,(int,float)) for value in values_raw):
            self.output_widget.update_plots(values_raw,frequencies_raw)

            self.status_bar.showMessage('Data successfully calculated', 5000)

        else:
            # error
            self.status_bar.showMessage('Error',5000)
            self.clear_output_widget()

    def get_data_from_input_table(self):
        input_table = self.input_widget.input_table
        input_table.clearFocus()
        rows = input_table.rowCount()
        values = []
        frequencies = []

        for row in range(rows):
            value_item = input_table.item(row, 0)
            frequency_item = input_table.item(row, 1)
            if value_item is not None and frequency_item is not None:
                try:
                    value = float(value_item.text())
                    if (value).is_integer():
                        value = int(value)

                except ValueError:
                    value = value_item.text()

                try:
                    frequency = abs(int(frequency_item.text()))
                except ValueError:
                    frequency = None

                if value != None and frequency != None:
                    values.append(value)
                    frequencies.append(frequency)

        # returns [], [] if all values are invalid
        return values, frequencies
        

    def create_button(self,text=None,tooltip=None,function=None,icon=None,iconsize=QSize(24,24)):
        btn = QPushButton(text)
        btn.setFont(QFont('Arial',8,QFont.Bold))
        btn.setIcon(icon)
        btn.setIconSize(iconsize)
        btn.setToolTip(tooltip)
        if function:
           btn.clicked.connect(function)
        return btn

    def create_action(self,tooltip=None,function=None,icon=None):
        action = QAction(icon,tooltip,self)
        action.triggered.connect(function)
        return action


    def update_plots(self, data_ranges, frequencies):

        self.output_widget.update_plots(data_ranges, frequencies)

    def bell_shape_function(self, x, mu, peak):
        # Simple bell-shaped function
        return int(peak * (1 - ((x - mu) / mu) ** 2))

    def plot_bell_shaped(self):
        # Example data for plotting
        N = randint(30, 40)
        uniform_width = 10
        data_ranges = [(i, i + uniform_width) for i in range(0, N * uniform_width, uniform_width)]
        middle_pos = (N + 1) // 2
        frequencies = [self.bell_shape_function(i, middle_pos, randint(90, 100)) for i in range(N)]

        # Plot histogram
        self.update_plots(data_ranges, frequencies)

        return data_ranges, frequencies

    def plot_right_skewed(self):
        # Example data for plotting
        N = randint(30,40)
        uniform_width = 10
        data_ranges = [(i, i + uniform_width) for i in range(0, N * uniform_width, uniform_width)]

        frequencies = generate_right_skewed_dist(N)

        # Plot histogram
        self.update_plots(data_ranges, frequencies)

        return data_ranges, frequencies

    def plot_left_skewed(self):
        # Example data for plotting
        N = randint(30,40)
        uniform_width = 10
        data_ranges = [(i, i + uniform_width) for i in range(0, N * uniform_width, uniform_width)]

        frequencies = generate_left_skewed_dist(N)

        # Plot histogram
        self.update_plots(data_ranges, frequencies)

        return data_ranges, frequencies

    def plot_random(self):

        if self.counter == 1:
            values, frequencies = self.plot_bell_shaped()
        elif self.counter == 2:
            values, frequencies = self.plot_right_skewed()
        elif self.counter == 3:
            values, frequencies = self.plot_left_skewed()
        elif self.counter == 4:
            values = [6, 7, 8, 9, 10, 11]
            frequencies = [3, 32, 19, 29, 11, 6]

            self.update_plots(values, frequencies)
        elif self.counter == 5:
            values = [(0,10),(10,25),(25,35),(35,40),(40,50)]
            frequencies = [3,19,21,5,2]

            self.update_plots(values, frequencies)

        elif self.counter == 6:
            values = [(0,50),(50,100),(100,200),(200,500)]
            frequencies = [43,31,25,21]

            self.update_plots(values,frequencies)

        self.counter += 1
        if self.counter == 7:
            self.counter = 1

        # Update input table
        self.update_input_table(values, frequencies)

        # Update status bar
        self.status_bar.showMessage('Data successfully generated', 5000)


    def update_input_table(self, values, frequencies):
        input_table = self.input_widget.input_table
        input_table.setRowCount(0) # Clear current data from input table
        input_table.setRowCount(len(values))

        for row in range(len(values)):

            # Handle values
            value = values[row]
            value = str(value) if not isinstance(value,tuple) else f'{min(value)}-{max(value)}'

            value_item = QTableWidgetItem(value)
            frequency_item = QTableWidgetItem(str(frequencies[row]))

            input_table.setItem(row,0,value_item)
            input_table.setItem(row,1,frequency_item)


def gui_darkstyle():
    import breeze_resources
    file = QFile(":/dark/stylesheet.qss")
    file.open(QFile.ReadOnly | QFile.Text)
    stream = QTextStream(file)
    darkstyle = stream.readAll()

    return darkstyle


if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyleSheet(gui_darkstyle())

    mainWindow = MainWindow()
    mainWindow.show()
    sys.exit(app.exec_())
