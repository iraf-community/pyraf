' This is a proof-of-concept for creating shortcuts on MS Windows.
' To run this script, put it in a file named something.vbs and then
'
' c:\> cscript something.vbs
'
' ( so, like os.system() from python or something like that. )  It
' appears that cscript is available at least on windows/xp and
' windows7.
'
' A general discussion where the outline of this script came from:
' http://stackoverflow.com/questions/346107/creating-a-shortcut-for-a-exe-from-a-batch-file
' http://www.tomshardware.com/forum/52871-45-creating-desktop-shortcuts-command-line
'
' Documentation of special folders:
' http://msdn.microsoft.com/en-us/library/system.environment.specialfolder.aspx
'
' About cscript:
' http://technet.microsoft.com/en-us/library/bb490816.aspx
' http://www.microsoft.com/resources/documentation/windows/xp/all/proddocs/en-us/wsh_runfromcommandprompt.mspx?mfr=true
'
' This language is VBScript.

sub make_shortcut( sp_folder )
	' look up the location of the special folder where we want the shortcut to appear
	set sh = WScript.CreateObject("WScript.Shell" )
	where = sh.SpecialFolders(sp_folder)

	' append the name we want for the shortcut
	where = where & "\pyraf.lnk"

	' create an in-memory object for the shortcut
	set link = sh.CreateShortcut( where )

	' set various attributes of the shortcut
	' (this part needs work)
	link.TargetPath = "c:\python27\scripts\runpyraf.py"
	link.WindowStyle = 1
	link.IconLocation = "c:\application folder\application.ico"
	link.Description = "Pyraf"
	link.WorkingDirectory = "c:\application folder"

	' actually write the shortcut to disk
	link.Save
end sub

' create the shortcuts in various places
make_shortcut( "Desktop" )
make_shortcut( "StartMenu" )
