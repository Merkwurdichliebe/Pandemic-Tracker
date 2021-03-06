from PySide2.QtWidgets import QTextEdit, QWidget, QHBoxLayout, QVBoxLayout,\
    QLabel, QPushButton, QGroupBox, QRadioButton, QComboBox, QScrollArea,\
    QButtonGroup, QFrame
from PySide2.QtCore import Qt, QSize, Signal
from enum import Enum
import bisect
import logging


###############################################################################
# Interface constants, sizes and colors
###############################################################################


WINDOW_H_SIZE = 1100
WINDOW_V_SIZE = 700
SPACING = 5                 # Vertical spacing of buttons
SPACER = 20                 # Vertical spacer
WIDTH = 150                 # Width of buttons and layout columns
HEIGHT = 24                 # Height of buttons
WIDTH_WITH_SCROLL = 176
TOP_CARDS = 16              # Number of Pool Selector buttons to display

COLOR = {
    'blue': '#4073bf',
    'black': '#404040',
    'yellow': '#e6ac00',
    'red': '#df4620',
    'green': '#009933',
    'gray': '#bfbfbf'
}


class ButtonCSS(Enum):
    """Stylesheets for active and inactive cardpool buttons
    displayed in the Draw Deck column"""
    Active = 'background: #999999; color: black; font-weight: bold;'
    Inactive = 'background: #dddddd; color: black; font-weight: bold;'
    MouseEnter = 'background: black; color: white; font-weight: bold;'


###############################################################################
# Various interface elements
###############################################################################


class Heading(QLabel):
    def __init__(self, text):
        super().__init__()
        self.setText(f'<h4>{text}</h4>')
        self.setAlignment(Qt.AlignHCenter)


class HLine(QFrame):
    def __init__(self):
        super(HLine, self).__init__()
        self.setFrameShape(QFrame.HLine)
        self.setFrameShadow(QFrame.Sunken)
        self.setFixedHeight(10)


class AppButtons(QVBoxLayout):
    def __init__(self):
        super().__init__()
        self.setSpacing(SPACING)
        self.button_new_game = QPushButton('New Game')
        self.addWidget(self.button_new_game)
        self.button_help = QPushButton('Help')
        self.addWidget(self.button_help)


class EpidemicMenu(QVBoxLayout):
    def __init__(self):
        super().__init__()
        self.setSpacing(SPACING)
        self.addWidget(Heading('Epidemic'))
        self.combo_box = QComboBox()
        self.addWidget(self.combo_box)
        # self.btn_shuffle_epidemic.clicked.connect(self.app.cb_epidemic)
        self.button = QPushButton('Shuffle Epidemic')
        self.addWidget(self.button)


class DestinationRadioBox(QGroupBox):
    def __init__(self, destinations):
        super().__init__()
        label = Heading('Card Destination')
        label.setMinimumWidth(WIDTH)
        label.setAlignment(Qt.AlignHCenter)
        box = QVBoxLayout()
        box.addWidget(label)

        # Subclass QGroupBox for the *visual* container
        self.setMaximumWidth(WIDTH_WITH_SCROLL)

        # QButtonGroup is used for the *logical* grouping
        self.b_group = QButtonGroup()

        for button in destinations.values():
            self.b_group.addButton(button)
            box.addWidget(button)
        self.setLayout(box)


class Stats(QVBoxLayout):
    def __init__(self):
        super().__init__()
        self.addWidget(Heading('Stats'))
        self._text = QLabel()
        self._text.setTextFormat(Qt.RichText)
        self.addWidget(self._text)
        self._max_cards = 10

    def show(self, stats):
        text = f'<p>Total cards in game: {stats.total}</p>'
        text += f'<p>In discard pile: {stats.in_discard}</p>'
        if stats.deck['draw'].is_empty():
            text += '<p>(Draw Deck is empty)</p>'
        else:
            text += f'<p><strong>Top probability:'
            text += f'{stats.percentage:.2%}</strong></p>'
            if len(stats.top_cards) < self._max_cards:
                text += '<ul>'
                for card in stats.top_cards:
                    text += f'<li>{card.name}</li>'
                text += '</ul>'
            else:
                text += f'<p>({self._max_cards}+ cards)</p>'
            text += f'<p>({stats.top_freq} of each)</p>'
        self._text.setText(text)


###############################################################################
# Pool selector & card pool
###############################################################################


class PoolButton(QLabel):
    clicked = Signal()

    def __init__(self):
        super().__init__()
        self.setAlignment(Qt.AlignCenter)
        self.active = None
        self.set_active(False)
        self.connected = False
        self.setFixedSize(QSize(WIDTH, HEIGHT))

    def set_connected(self, connected):
        self.connected = connected

    def is_connected(self):
        return self.connected

    def set_active(self, active):
        self.active = active
        self.setStyleSheet(
            ButtonCSS.Active.value if active else ButtonCSS.Inactive.value)
        self.repaint()  # Fix Qt bug on macOS

    def mouseReleaseEvent(self, event):
        self.clicked.emit()

    def enterEvent(self, event):
        if self.isEnabled():
            self.setStyleSheet(ButtonCSS.MouseEnter.value)

    def leaveEvent(self, event):
        if self.isEnabled() and self.active:
            self.setStyleSheet(ButtonCSS.Active.value)
        else:
            self.setStyleSheet(ButtonCSS.Inactive.value)

    def set_text(self, text):
        self.setText(text)
        self.repaint()  # Fix Qt bug on macOS


class PoolSelector(QVBoxLayout):
    def __init__(self, count):
        super().__init__()
        self.addWidget(Heading('INFECTION DECK'))
        v_buttons = QVBoxLayout()
        v_buttons.setSpacing(SPACING)
        self.addLayout(v_buttons)
        self.button = []
        for i in range(count):
            btn = PoolButton()
            btn.set_active(False)
            self.button.append(btn)
            v_buttons.addWidget(btn)


class Log(QFrame):
    def __init__(self):
        super().__init__()
        # QFrame needs an object name so that its stylesheet border
        # isn't applied to the QTextEdit child widget
        self.setObjectName('log-frame')
        style = f'border: 1px solid {COLOR["gray"]}; border-radius: 5px;'
        self.setStyleSheet('QFrame#log-frame {' + style + '}')
        layout = QVBoxLayout()
        self.setLayout(layout)

        # CSS selector set specifically to QTextEdit
        # otherwise scrollbar appearance is modified
        self.edit = QTextEdit()
        self.edit.setStyleSheet('QTextEdit {background-color: transparent}')
        self.edit.setReadOnly(True)
        layout.addWidget(self.edit)

    def log(self, text):
        self.edit.append(text)

    def clear(self):
        self.edit.clear()


class Cardpool(QVBoxLayout):
    def __init__(self):
        super().__init__()
        self.addWidget(Heading(''))
        self._text = QLabel()
        self._text.setTextFormat(Qt.RichText)
        self._text.setWordWrap(True)
        self._text.setFixedWidth(WIDTH)
        self.addWidget(self._text)
        self.addStretch()
        self._max_cards = 35

    def show_empty(self):
        self._text.setText(f'<p>Draw Deck is empty.</p>')

    def show(self, deck_name, position, deck):
        text = f'<p>Card position: {position}</p>'
        text += f'<p>(from {deck_name})<p>'
        text += f'<p><strong>Possible cards:</strong></p>'
        if len(deck) < self._max_cards:
            for card in sorted(set(deck.cards), key=lambda x: x.name):
                text += f'{card.name} ({deck.cards.count(card)})<br>'
        else:
            text += f'{self._max_cards}+ cards'
        self._text.setText(text)


###############################################################################
# Decks
###############################################################################


class CardButton(QLabel):
    clicked = Signal()

    def __init__(self, card):
        super().__init__(card.name)
        self.card = card
        self.color = None
        self.stylesheet = None
        self.setAlignment(Qt.AlignCenter)
        self.setFixedSize(QSize(WIDTH, HEIGHT))

    def set_color(self, color):
        self.color = color
        self.stylesheet = f'background: {self.color};' \
                          f'color: white;' \
                          f'font-weight: bold;'
        self.setStyleSheet(self.stylesheet)

    def mouseReleaseEvent(self, event):
        self.clicked.emit()

    def enterEvent(self, event):
        self.setStyleSheet(ButtonCSS.MouseEnter.value)

    def leaveEvent(self, event):
        self.setStyleSheet(self.stylesheet)


class Deck(QVBoxLayout):
    def __init__(self, heading, color=True):
        super().__init__()
        logging.info(f'[Deck] {heading} init')
        self.addWidget(Heading(heading))
        self.use_color = color
        self.cards = []
        self.buttons = []
        self.heading = heading

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.addWidget(self.scroll_area)

        self.v_scroll = QVBoxLayout()
        self.v_scroll.setSpacing(SPACING)
        self.v_scroll.addStretch()

        self.scroll_widget = QWidget()
        self.scroll_widget.setLayout(self.v_scroll)
        self.scroll_area.setFixedWidth(WIDTH_WITH_SCROLL)
        self.scroll_area.setWidget(self.scroll_widget)

    def add_card_button(self, card):
        return self.insert_button_at_index(card, 0)

    def insert_button_at_index(self, card, index):
        button = CardButton(card)
        self.v_scroll.insertWidget(index, button)
        color = COLOR[card.color] if self.use_color else COLOR['gray']
        button.set_color(color)
        self.cards.insert(index, card.name)
        self.buttons.append(button)
        return button

    def remove_card_button(self, button):
        self.cards.remove(button.card.name)
        self.buttons.remove(button)
        self.removeWidget(button)
        button.deleteLater()

    def clear(self):
        logging.info(f'[Deck] clear {self.heading}')
        for button in self.buttons:
            button.deleteLater()
        self.cards.clear()
        self.buttons.clear()


class DrawDeck(Deck):
    def __init__(self, heading):
        super().__init__(heading)

    def add_card_button(self, card):
        # Override base method, use bisect to insert
        # the card into the Draw Deck in sorted order
        if card.name not in self.cards:
            index = bisect.bisect_left(self.cards, card.name)
            return super().insert_button_at_index(card, index)
        else:
            print(f'[qt DrawCardDeck] {card.name} already in layout')
            return None


###############################################################################
# Main window
###############################################################################

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        logging.info(f'[MainWindow] init')

        self.top_cards = TOP_CARDS
        self.cardpool = Cardpool()
        self.pool_selector = PoolSelector(self.top_cards)
        self.log = Log()
        # self.setFixedSize(WINDOW_H_SIZE, WINDOW_V_SIZE)

        # To allow quitting when canceling new game dialog at launch
        self.has_initialised = False

        self.deck = {
            'draw': DrawDeck('DRAW CARD'),
            'discard': Deck('DISCARD PILE'),
            'exclude': Deck('EXCLUDED', color=False)
        }

        self.app_buttons = AppButtons()

        self.destination = {
            'draw_top': QRadioButton('Infection (Top)'),
            'draw_bottom': QRadioButton('Infection (Bottom)'),
            'draw_single': QRadioButton('Infection (Single)'),
            'discard_deck': QRadioButton('Discard'),
            'exclude_deck': QRadioButton('Exclude')
        }
        self.destinations = DestinationRadioBox(self.destination)
        self.epidemic_menu = EpidemicMenu()
        self.stats = Stats()

        self.setWindowTitle('Epidemic')

        # Global parent container
        v_app = QVBoxLayout()
        self.setLayout(v_app)

        # Main horizontal container
        h_main = QHBoxLayout()
        v_app.addLayout(h_main)

        # Left layout (cardpool, selector and log)
        v_left = QVBoxLayout()

        v_left_upper = QHBoxLayout()
        v_left.addLayout(v_left_upper)

        v_left_upper.addLayout(self.cardpool)
        v_left_upper.addLayout(self.pool_selector)

        v_left_lower = QHBoxLayout()
        v_left.addLayout(v_left_lower)

        v_left_lower.addWidget(self.log)

        h_main.addLayout(v_left)

        # Decks
        h_main.addLayout(self.deck['draw'])
        h_main.addLayout(self.deck['discard'])
        h_main.addLayout(self.deck['exclude'])

        # Right sidebar
        v_sidebar = QVBoxLayout()
        v_sidebar.addWidget(Heading(' '))
        v_sidebar.addLayout(self.app_buttons)
        v_sidebar.addWidget(self.destinations)
        v_sidebar.addLayout(self.epidemic_menu)
        v_sidebar.addLayout(self.stats)
        v_sidebar.addStretch()

        h_main.addLayout(v_sidebar)
        h_main.addStretch()

    def initialise(self):
        logging.info(f'[Main Window] initialise')
        self.destination['exclude_deck'].setChecked(True)
        for k, v in self.deck.items():
            self.deck[k].clear()
        self.has_initialised = True
