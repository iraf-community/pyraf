#
# A home-grown list-selection convenience dialog.  As *soon* as tkinter comes
# with one of these, replace all uses of this one with that.  This currently
# only allows single selection.
#
"""
$Id$
"""
from . import capable, irafutils

if capable.OF_GRAPHICS:
    from tkinter import *  # noqa
    from tkinter.simpledialog import Dialog
else:
    Dialog = object


class ListSingleSelectDialog(Dialog):

    def __init__(self, title, prompt, choiceList, parent=None):

        if not parent:
            parent = irafutils.init_tk_default_root()

        self.__prompt = prompt
        self.__choices = choiceList
        self.__retval = None
        self.__clickedOK = False
        parent.update()
        Dialog.__init__(self, parent, title) # enters main loop here


    def get_current_index(self):
        """ Return currently selected index (or -1) """

        # Need to convert to int; currently API returns a tuple of string
        curSel = self.__lb.curselection()
        if curSel and len(curSel) > 0:
            return int(curSel[0])
        else:
            return -1


    def getresult(self): return self.__retval


    def destroy(self):
        # first save the selected index before it is destroyed
        idx = self.get_current_index()
        # in PyRAF, assume they meant the first one if they clicked nothing,
        # since it is already active (underlined)
        if idx < 0: idx = 0
        # get the object at that index
        if self.__clickedOK and idx >= 0: # otherwise is None
            self.__retval = self.__choices[idx]
        if self.__retval and type(self.__retval) == str:
            self.__retval = self.__retval.strip()

        # now destroy
        self.__lb = None
        Dialog.destroy(self)


    def body(self, master):

        label = Label(master, text=self.__prompt, justify=LEFT)
#       label.grid(row=0, padx=8, sticky=W)
        label.pack(side=TOP, fill=X, padx=10, pady=8)

        frame = Frame(master)
#       frame.grid(row=1, padx=8, sticky=W+E)
        frame.pack(side=TOP, fill=X, padx=10, pady=8)

        vscrollbar = Scrollbar(frame, orient=VERTICAL)
        hscrollbar = Scrollbar(frame, orient=HORIZONTAL)
        self.__lb = Listbox(frame,
                            selectmode=BROWSE,
                            xscrollcommand=hscrollbar.set,
                            yscrollcommand=vscrollbar.set)
#                           activestyle='none', # none = dont underline items
        hscrollbar.config(command=self.__lb.xview)
        hscrollbar.pack(side=BOTTOM, fill=X)
        vscrollbar.config(command=self.__lb.yview)
        vscrollbar.pack(side=RIGHT, fill=Y)
        self.__lb.pack(side=LEFT, fill=BOTH, expand=1)

        for itm in self.__choices:
            self.__lb.insert(END, str(itm))

        self.__lb.bind("<Double-Button-1>", self.ok) # dbl clk
#       self.__lb.selection_set(0,0)
        self.__lb.focus_set()

        return self.__lb

    def ok(self, val=None):
        self.__clickedOK = True # save that this wasn't a cancel
        Dialog.ok(self, val)

    def validate(self): return 1


if __name__ == "__main__":
    """This is for manual testing only because it is interactive."""
    root = Tk()
    root.withdraw()
    root.update()
    x = ListSingleSelectDialog("Select Parameter File", \
                               "Select which file you prefer for task/pkg:", \
                               ['abc','def','ghi','jkl','1'], None)
    print(str(x.getresult()))
