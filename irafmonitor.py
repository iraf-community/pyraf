from Tkinter import *
from ScrolledText import ScrolledText

class IRAFmonitor(Frame):

	def __init__(self, parent=None):

		top = Toplevel()
		Frame.__init__(self,top)
		self.pack()
		self.text = ScrolledText(self, height=30, width=90)
		self.text.pack()
		self.linecount = 0

	def append(self, text):

		self.text.insert('9999.0', '%8d | %s' % (self.linecount,text))
		self.linecount = self.linecount + 1
