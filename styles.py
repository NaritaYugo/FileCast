from dataclasses import dataclass


@dataclass
class MainStyle:
    DIR_LABEL = "background-color: #2b2b2b; color: white; padding: 5px;"
    TABLE_PH = "color:gray; font-size: 16px"
    SETTING_BTN = "background-color: #007ACC; color: white; padding: 10px 30px;"
    RULES_SAMPLE = "background-color: white; padding: 10px 30px;"
    EXECUTE_BTN = "background-color: #d9534f; color: white; padding: 10px 30px;"

@dataclass
class RuleStyle:
    RULE_BLOCK_LIST = """
        QListWidget {
            background-color: #2b2b2b;
            outline: none;
            padding :5px;
            border-radius: 4px;
        }
        QListWidget::item {
            background-color:#555;
            color:white;
            margin:2px;
            min-width:100px;
            border-radius: 3px;
        }
        QListWidget::item:selected {
            background-color: #007ACC;
        }

        QScrollBar:horizontal {
            background-color: #2b2b2b;
            height: 8px;
            margin: 0px 0px 0px 0px;
        }
        QScrollBar::handle:horizontal {
            background-color: #007ACC;
            min-width: 20px;
            border-radius: 2px;
            margin: 2px;
        }
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
            width: 0px;
        }
        QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
            background: none;
        }
        """

    PALLETE_LIST = """
        QListWidget {
            background-color: #222;
            padding: 10px; 
            border-radius: 
            4px; 
        }
        QListWidget::item {
            background-color: #555; 
            color: white; 
            margin: 2px;
            padding: 4px 4px; 
            border-radius: 3px;
        }

        QScrollBar:vertical {
            background-color: #222222;
            width: 8px;
            margin: 0px 0px 0px 0px;
        }
        QScrollBar::handle:vertical {
            background-color: #007ACC;
            min-height: 20px;
            border-radius: 2px;
            margin: 2px;
        }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            height: 0px;
        }
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
            background: none;
        }
        """

    DELETE_BLOCK_BTN = """
        QPushButton {
            background-color: #d9534f;
            color: white;
            border-radius: 7px; 
            font-size: 9px; 
            font-weight: bold; 
            border: none;
            line-height: 14px;
        }
        QPushButton:hover {
            background-color: #c9302c;
        }
        """

    RULE_BLOCK_LABEL = "color: white; font-weight: bold; background: transparent;"

    SAMPLE_LABEL = "padding: 3px;"