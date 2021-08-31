#!/usr/bin/env  python3
"""
A filechooser for urwid.
Author: Rebecca Breu (rebecca@rbreu.de)
License: GPL

In use with PyRAF until a File-Browser/Chooser comes standard with Urwid. This
copy is based on r49 of urwid/contrib/trunk/rbreu_filechooser.py, updated
2006.10.17.  Only minor changes were made - mostly to handle use with differing
versions of urwid.  Many thanks to author Rebecca Breu.
"""


from urwid import (Text, AttrWrap, WidgetWrap, BoxAdapter, ListBox, AttrWrap,
                   Columns, Edit, Button, GridFlow, CheckBox, Pile,
                   SimpleListWalker)

import os
from os.path import normpath, abspath, join

__all__ = ["FileChooser"]


######################################################################
class SelText(Text):
    """
    A selectable text widget. See urwid.Text.
    """

    def selectable(self):
        """
        Make widget selectable.
        """
        return True

    def keypress(self, size, key):
        """
        Don't handle any keys.
        """
        return key


######################################################################
class FileChooser(WidgetWrap):
    """
    Creates a dialog (FlowWidget) for choosing a file.

    It displays the subdirectories and files in the selected directory in two
    different ListBoxes, and the whole filename of the selected file in an
    Edit widget. The user can choose from the ListBoxes, or type an arbitrary
    path in the Edit widget. After pressing enter in the Edit widget, the
    ListBoxes will be updated accordingly.

    The FileChooser has some text in English, but one can easiliy create a new
    widget inheriting from FileChooser and alter the string constants
    SELECTION_TEXT and SHOW_HIDDEN_TEXT.
    """

    SELECTION_TEXT = "Selection"
    SHOW_HIDDEN_TEXT = "Show hidden files"

    selection = None
    b_pressed = None

    _blank = Text("")

    def __init__(self,
                 height,
                 directory=".",
                 file="",
                 attr=(None, None),
                 show_hidden=False):
        """
        height -- height of the directory list and the file list
        directory, file -- default selection
        attr -- (inner selectable widgets, selected widgets)
        show_hidden -- If True, hidden files are shown by default.
        """

        self.directory = abspath(directory)
        self.file = ""
        self.attr = attr
        self.height = height
        self.show_hidden = show_hidden

        # Create dummy widgets for directory and file display:
        self.dir_widget = AttrWrap(
            BoxAdapter(ListBox([self._blank]), self.height), self.attr[0])
        self.file_widget = AttrWrap(
            BoxAdapter(ListBox([self._blank]), self.height), self.attr[0])

        columns = Columns([self.dir_widget, self.file_widget], 1)

        # Selection widget:
        self.select_widget = AttrWrap(Edit("", ""), self.attr[0], self.attr[1])

        # Buttons and checkbox:
        button_widgets = [
            AttrWrap(Button(button, self._action), attr[0], attr[1])
            for button in ["OK", "Cancel"]
        ]
        button_grid = GridFlow(button_widgets, 12, 2, 1, 'center')

        button_cols = Columns([
            CheckBox(self.SHOW_HIDDEN_TEXT, self.show_hidden, False,
                     self._toggle_hidden), button_grid
        ])

        self.outer_widget = Pile([
            columns, self._blank,
            Text(self.SELECTION_TEXT), self.select_widget, self._blank,
            button_cols
        ])

        self.update_widgets()

        WidgetWrap.__init__(self, self.outer_widget)

    def _dirfiles(self, directory):
        """
        Get a list of all directories and files in directory.
        List contains hidden files/dirs only if self.show_hidden is True.
        """

        dirlist = [".", ".."]
        filelist = []

        for entry in os.listdir(directory):
            path = os.path.join(directory, entry)
            if self.show_hidden or not entry.startswith("."):
                if os.path.isdir(path):
                    dirlist.append(entry)
                elif os.path.isfile(path):
                    filelist.append(entry)
                else:
                    pass

        return (dirlist, filelist)

    def update_widgets(self,
                       update_dir=True,
                       update_file=True,
                       update_select=True):
        """
        Update self.dir_widget, self.file_widget or self.select_widget,
        corresponding to which of the paramters are set to True.
        """

        if update_dir or update_file:
            (dirlist, filelist) = self._dirfiles(self.directory)

        if update_dir:
            # Directory widget:
            widget_list = [
                AttrWrap(SelText(dir), None, self.attr[1]) for dir in dirlist
            ]

            self.dir_widget.box_widget.body = SimpleListWalker(widget_list)

        if update_file:
            # File widget:
            widget_list = [
                AttrWrap(SelText(dir), None, self.attr[1]) for dir in filelist
            ]

            self.file_widget.box_widget.body = SimpleListWalker(widget_list)

        if update_select:
            # Selection widget:
            selected_file = join(self.directory, self.file)
            self.select_widget.set_edit_text(selected_file)

    def _focused_widgets(self):
        """
        Return a list of focused widgets.
        """

        focused = [self.outer_widget]
        widget = self.outer_widget

        while hasattr(widget, "get_focus"):
            widget = widget.get_focus()
            try:
                focused.append(widget[0])
            except (TypeError, AttributeError):
                focused.append(widget)

        return focused

    def _action(self, button):
        """
        Function called when a button is pressed.
        Should not be called manually.
        """

        if button.get_label() == "OK":
            self.selection = self.select_widget.get_edit_text()

        self.b_pressed = button.get_label()

    def _toggle_hidden(self, checkbox, new_state):
        """
        Function called when the \"Show hidden files\" checkbox
        ist toggled.
        Should not be called manually.
        """

        self.show_hidden = new_state
        self.update_widgets(True, True)

    def keypress(self, size, key):
        """
        <RETURN> key selects a path or file, other keys will be passed to
        the Pile widget.
        """

        if key == "enter":
            focused = self._focused_widgets()
            if focused[-2] == self.dir_widget:
                # User has selected a directory from the list:
                new_dir = focused[-1].w.get_text()[0]
                self.directory = normpath(join(self.directory, new_dir))
                self.file = ""
                self.update_widgets()
                return
            elif focused[-2] == self.file_widget:
                # User has selected a file from the list:
                self.file = focused[-1].w.get_text()[0]
                self.update_widgets(False, False, True)
                return
            elif focused[-1] == self.select_widget:
                # User has pressed enter in the "Selection Widget":
                path = self.select_widget.get_edit_text()
                (self.directory, self.file) = os.path.split(path)
                self.update_widgets(True, True, False)
                return

        return self.outer_widget.keypress(size, key)

    def mouse_event(self, size, event, button, col, row, focus):
        """
        First mouse button selects a path or file, other keys will be passed to
        the Pile widget.
        """
        handled = self.outer_widget.mouse_event(size, event, button, col, row,
                                                focus)

        if event == "mouse press" and button == 1:
            focused = self._focused_widgets()
            if focused[-2] == self.dir_widget:
                # User has selected a directory from the list:
                new_dir = focused[-1].w.get_text()[0]
                self.directory = normpath(join(self.directory, new_dir))
                self.file = ""
                self.update_widgets()
                return
            elif focused[-2] == self.file_widget:
                # User has selected a file from the list:
                self.file = focused[-1].w.get_text()[0]
                focus = (self.dir_widget.get_focus()[1],
                         self.file_widget.get_focus()[1])
                self.update_widgets(False, False, True)
                return

            handled = True

        return handled


######################################################################
# End of module part
######################################################################

import urwid


def main():

    global selection
    global ui

    ui = urwid.curses_display.Screen()

    ui.register_palette([
        ('menu', 'black', 'dark cyan', 'standout'),
        ('menuf', 'black', 'light gray'),
        ('bg', 'light gray', 'dark blue'),
    ])

    return ui.run_wrapper(run)


def run():

    global selection
    global ui

    ui.set_mouse_tracking()
    dim = ui.get_cols_rows()

    widget = urwid.Filler(FileChooser(height=10, attr=("menu", "menuf")))
    widget = urwid.AttrWrap(widget, "bg")

    keys = True

    while True:
        if keys:
            ui.draw_screen(dim, widget.render(dim, True))

        keys = ui.get_input()

        if widget.body.b_pressed == "OK":
            selection = "You selected: " + widget.body.selection
            return widget.body.selection

        if widget.body.b_pressed == "Cancel":
            selection = "No file selected."
            return

        if "window resize" in keys:
            dim = ui.get_cols_rows()

        for k in keys:
            if urwid.is_mouse_event(k):
                event, button, col, row = k
                widget.mouse_event(dim, event, button, col, row, focus=True)
            else:
                widget.keypress(dim, k)


if __name__ == "__main__":
    import urwid
    import urwid.curses_display
    print(main())
