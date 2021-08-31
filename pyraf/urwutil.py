#
# Urwid example similar to dialog(1) program
#    Copyright (C) 2004-2007  Ian Ward
#
#    This library is free software; you can redistribute it and/or
#    modify it under the terms of the GNU Lesser General Public
#    License as published by the Free Software Foundation; either
#    version 2.1 of the License, or (at your option) any later version.
#
#    This library is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#    Lesser General Public License for more details.
#
#    You should have received a copy of the GNU Lesser General Public
#    License along with this library; if not, write to the Free Software
#    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
# Urwid web site: http://excess.org/urwid/
"""
July 2008 - taken from the urwid example script "dialog.py", for the use of
the DialogDisplay and the InputDialogDisplay classes.  Unsure why this
functionality is not delivered with a standard urwid installation, so we will
include this file until it comes with urwid.  This is slightly modified.
"""


import sys
import urwid
import urwid.raw_display


class DialogExit(Exception):
    pass


class DialogDisplay:
    palette = [
        ('body', 'black', 'light gray', 'standout'),
        ('border', 'black', 'dark blue'),
        ('shadow', 'white', 'black'),
        ('selectable', 'black', 'dark cyan'),
        ('focus', 'white', 'dark blue', 'bold'),
        ('focustext', 'light gray', 'dark blue'),
    ]

    def __init__(self, text, height, width, body=None):
        width = int(width)
        if width <= 0:
            width = ('relative', 80)
        height = int(height)
        if height <= 0:
            height = ('relative', 80)

        self.body = body
        if body is None:
            # fill space with nothing
            body = urwid.Filler(urwid.Divider(), 'top')

        self.frame = urwid.Frame(body, focus_part='footer')
        if text is not None:
            self.frame.header = urwid.Pile([urwid.Text(text), urwid.Divider()])
        w = self.frame

        # pad area around listbox
        w = urwid.Padding(w, ('fixed left', 2), ('fixed right', 2))
        w = urwid.Filler(w, ('fixed top', 1), ('fixed bottom', 1))
        w = urwid.AttrWrap(w, 'body')

        # "shadow" effect
        w = urwid.Columns([
            w,
            ('fixed', 2,
             urwid.AttrWrap(urwid.Filler(urwid.Text(('border', '  ')), "top"),
                            'shadow'))
        ])
        w = urwid.Frame(w,
                        footer=urwid.AttrWrap(urwid.Text(('border', '  ')),
                                              'shadow'))

        # outermost border area
        w = urwid.Padding(w, 'center', width)
        w = urwid.Filler(w, 'middle', height)
        w = urwid.AttrWrap(w, 'border')

        self.view = w

    def add_buttons(self, buttons):
        l = []
        for name, exitcode in buttons:
            b = urwid.Button(name, self.button_press)
            b.exitcode = exitcode
            b = urwid.AttrWrap(b, 'selectable', 'focus')
            l.append(b)
        self.buttons = urwid.GridFlow(l, 10, 3, 1, 'center')
        self.frame.footer = urwid.Pile([urwid.Divider(), self.buttons],
                                       focus_item=1)

    def button_press(self, button):
        raise DialogExit(button.exitcode)

    def main(self):
        self.ui = urwid.raw_display.Screen()
        self.ui.register_palette(self.palette)
        return self.ui.run_wrapper(self.run)

    def run(self):
        self.ui.set_mouse_tracking()
        size = self.ui.get_cols_rows()
        try:
            while True:
                canvas = self.view.render(size, focus=True)
                self.ui.draw_screen(size, canvas)
                keys = None
                while not keys:
                    keys = self.ui.get_input()
                for k in keys:
                    if urwid.is_mouse_event(k):
                        event, button, col, row = k
                        self.view.mouse_event(size,
                                              event,
                                              button,
                                              col,
                                              row,
                                              focus=True)
                    if k == 'window resize':
                        size = self.ui.get_cols_rows()
                    k = self.view.keypress(size, k)

                    if k:
                        self.unhandled_key(size, k)
        except DialogExit as e:
            return self.on_exit(e.args[0])

    def on_exit(self, exitcode):
        return exitcode, ""

    def unhandled_key(self, size, key):
        pass


class InputDialogDisplay(DialogDisplay):

    def __init__(self, text, height, width):
        self.edit = urwid.Edit()
        body = urwid.ListBox([self.edit])
        body = urwid.AttrWrap(body, 'selectable', 'focustext')

        DialogDisplay.__init__(self, text, height, width, body)

        self.frame.set_focus('body')

    def unhandled_key(self, size, k):
        if k in ('up', 'page up'):
            self.frame.set_focus('body')
        if k in ('down', 'page down'):
            self.frame.set_focus('footer')
        if k == 'enter' or k == 'ctrl m':  # STScI change ! add ctrl-m for OSX
            # pass enter to the "ok" button
            self.frame.set_focus('footer')
            self.view.keypress(size, 'enter')

    def on_exit(self, exitcode):
        return exitcode, self.edit.get_edit_text()


#
# ListDialogDisplay example:
#
# choices = ['a','b','c','d']
# import urwutil
# import urwid
# def mmm(tag, state): return urwutil.MenuItem(tag)
# chcs = []
# for itm in choices:
#    chcs.append(itm)
#    chcs.append('') # empty state
# dlg=urwutil.ListDialogDisplay("select: ", len(choices)+7,
#                               75, mmm, tuple(chcs), False)
# dlg.add_buttons([ ("Cancel",1), ])
# rv, item = dlg.main() # use item if rv == 0
#


class ListDialogDisplay(DialogDisplay):

    def __init__(self, text, height, width, constr, items, has_default):
        j = []
        if has_default:
            k, tail = 3, ()
        else:
            k, tail = 2, ("no",)
        while items:
            j.append(items[:k] + tail)
            items = items[k:]

        l = []
        self.items = []
        for tag, item, default in j:
            w = constr(tag, default == "on")
            self.items.append(w)
            w = urwid.Columns([('fixed', 12, w), urwid.Text(item)], 2)
            w = urwid.AttrWrap(w, 'selectable', 'focus')
            l.append(w)

        lb = urwid.ListBox(l)
        lb = urwid.AttrWrap(lb, "selectable")
        DialogDisplay.__init__(self, text, height, width, lb)

        self.frame.set_focus('body')

    def unhandled_key(self, size, k):
        if k in ('up', 'page up'):
            self.frame.set_focus('body')
        if k in ('down', 'page down'):
            self.frame.set_focus('footer')
        if k == 'enter':
            # pass enter to the "ok" button
            self.frame.set_focus('footer')
            self.buttons.set_focus(0)
            self.view.keypress(size, k)

    def on_exit(self, exitcode):
        """Print the tag of the item selected."""
        if exitcode != 0:
            return exitcode, ""
        s = ""
        for i in self.items:
            if i.get_state():
                s = i.get_label()
                break
        return exitcode, s


class MenuItem(urwid.Text):
    """A custom widget for the ListDialog"""

    def __init__(self, label):
        urwid.Text.__init__(self, label)
        self.state = False

    def selectable(self):
        return True

    # The change below (in the if) was made by STScI !
    def keypress(self, size, key):
        if key == "enter" or \
           key == "ctrl m" or key == " ": # is ctrl-m on OSX; also allow space
            self.state = True
            raise DialogExit(0)
        return key

    def mouse_event(self, size, event, button, col, row, focus):
        if event == 'mouse release':
            self.state = True
            raise DialogExit(0)
        return False

    def get_state(self):
        return self.state

    def get_label(self):
        text, attr = self.get_text()
        return text


def show_usage():
    """
    Display a helpful usage message.
    """
    sys.stdout.write(__doc__ + "\n\t" + sys.argv[0] + " text height width\n" +
                     """

height and width may be set to 0 to auto-size.
list-height and menu-height are currently ignored.
status may be either on or off.
""")


if __name__ == "__main__":

    if len(sys.argv) < 4:
        show_usage()
        sys.exit(1)

    # Create a DialogDisplay instance
    d = InputDialogDisplay(sys.argv[1], sys.argv[2], sys.argv[3])
    # for simple yes/no dialog:  d = DialogDisplay(text, height, width)
    d.add_buttons([("OK", 0), ("Cancel", 1)])

    # Run it
    exitcode, exitstring = d.main()

    # Exit
    if exitstring:
        sys.stderr.write(exitstring + "\n")
    sys.exit(exitcode)
