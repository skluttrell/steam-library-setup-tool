import collections, os, re, psutil, winreg, wx
from shutil import copy
from sys import exit

class SteamIsRunning(wx.Dialog):
	""" A custome dialog to show if Steam processes are running """

	def __init__(self, parent):
		super(SteamIsRunning, self).__init__(parent, title='Alert')
		panel = wx.Panel(self)
		self.msg = wx.StaticText(panel, wx.ID_ANY, 'Cannot proceed because Steam is running in the background. Please close the program and try again or override this check (not recommended).')
		self.tryButton = wx.Button(panel, wx.ID_OK, label='Try Again')
		self.OverrideButton = wx.Button(panel, wx.ID_CANCEL, label='Override')

class Window(wx.Frame):
	""" The main program window (frame) """

	def CheckForProcess(self, process):
		""" Checks to see if a given process is running """

		for p in psutil.process_iter():
			try:
				if p.name() == process:
					return True
			except:
				continue
		return False

	def FindSteamDirectory(self):
		""" Tries to locate the Steam directory """

		try:
			with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'Software\\Valve\\Steam') as k:
				# Acquires the steam executable location from the SteamKey located in the registry, then converts the slashes to backslashes, and finally strips the steam.exe file name from the end with os.path.dirname to get the root directory
				return os.path.dirname(winreg.QueryValueEx(k, 'SteamExe')[0].replace('/', '\\'))
		except:
			# Don't return anything if it fails to locate the registry key
			return

	def backup(self, file):
		""" Makes a backup copy of a given file """
		bFile = file + '.old' # add ".old" to the end of the file
		count = 1
		# If the file "whatever.old" already exists, I don't want to overwrite it.
		# So I added this loop here to add a number after the subsequent .olds to distinguish them.
		while os.path.exists(bFile):
			bFile += '.' + str(count)
			count += 1
		copy(file, bFile) # Finally make a backup copy of the file

	def isReady(self):
		""" Checks if Steam is running in the background and gathers some startup info. Note: user can overide this behavior (Not recommended). """

		# looks to see if steam.exe is a running process
		if self.CheckForProcess('steam.exe'):
			# If Steam is running, give the user a chance to shut it down or proceed anyway (override)
			with SteamIsRunning(self) as dlg:
				if dlg.ShowModal() == wx.ID_OK:
					self.isReady()

		# Get the directory for Steam
		self.steamPath = self.FindSteamDirectory()
		if not self.steamPath:
			with wx.DirDialog(self, 'Please select the directory where steam.exe resides', wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST) as dlg:
				if dlg.ShowModal() == wx.ID_OK:
					self.steamPath = dlg.GetPath()
				else:
					with wx.MessageDialog(self, 'Cannot proceed because the Steam folder could not be located.', 'Alert', wx.OK | wx.ICON_WARNING) as dlg:
						dlg.ShowModal()
					exit(0)

		# Ensure that the Steam libraryfolders.vdf file exists
		self.vdfFile = os.path.join(self.steamPath, 'steamapps', 'libraryfolders.vdf')
		if not os.path.exists(self.vdfFile):
			with wx.MessageDialog(self, 'Cannot proceed because a necessary file (libraryfolder.vdf) could not be located.', 'Alert', wx.OK | wx.ICON_WARNING) as dlg:
				dlg.ShowModal()
			exit(0)

		# Acquire any existing library folders
		info_t = collections.namedtuple( "info_t", ( "key", "value" ) )
		parent = ""
		libFolders = []

		with open(self.vdfFile, 'r') as inFile:
			for line in inFile:
				# Match for the parent item
				# This identifies the heading for a new group of key/value pairs
				match = re.match("^\"(.*)\"$", line)
				if match:
					parent = match.group( 1 )
					continue

				# Match for key and value
				match = re.match("^\s*\"(.*)\"\s*\"(.*)\"$", line)
				if match:
					if parent not in self.libInfo:
						self.libInfo[parent] = []
					self.libInfo[parent].append(info_t(key=match.group(1), value=match.group(2)))
					continue

		# Find the library folders
		for info in self.libInfo[ "LibraryFolders" ]:
			try:
				folder_id = int( info.key ) # Non integer values (strings) throw an exception: meaning this is not a library path value (it's some other necessary thing for Steam)
				libFolders.append(info) # Only keys with integers will make it here because those are actual library folders
				self.libPathsList.Append(info.value) # Place the folders in the list box control
			except ValueError:
				pass # ignore and move on to the next

		# Remove the library folders from the library info
		# They'll be added back in later
		for folder in libFolders:
			self.libInfo["LibraryFolders"].remove(folder)

	# Initialize the main program window (frame)
	def __init__(self, parent, title):
		super(Window, self).__init__(parent, title=title)
		panel = wx.Panel(self)
		mainSizer = wx.BoxSizer(wx.VERTICAL)
		buttonsSizer = wx.BoxSizer(wx.HORIZONTAL)
		self.steamPath = '' # The directory where steam resides
		self.vdfFile = '' # The configuration file that tells Steam what folders are available to use for game installations
		self.libInfo = {} # A copy of the information from the VDF file

		# Initialize the user interface elements
		self.libPathsList = wx.ListBox(panel) # List box to show the library paths
		self.acceptButton = wx.Button(panel, label='Accept') # Commit the changes to the VDF file
		self.addButton = wx.Button(panel, label='Add') # Add a new library path
		self.addButton.SetFocus() # Set this button as the focus when the app opens
		self.removeButton = wx.Button(panel, label='Remove') # Removes a path from the library paths list
		self.exitButton = wx.Button(panel, label='Exit') # Closes the app without committing any changes

		# link the elements to the sizers
		buttonsSizer.Add(self.acceptButton, 1, wx.EXPAND)
		buttonsSizer.Add(self.addButton, 1, wx.EXPAND)
		buttonsSizer.Add(self.removeButton, 1, wx.EXPAND)
		buttonsSizer.Add(self.exitButton, 1, wx.EXPAND)
		mainSizer.Add(self.libPathsList, 1, wx.EXPAND)
		mainSizer.Add(buttonsSizer, 1, wx.EXPAND)

		# Bind the event listeners to their respective controls
		self.acceptButton.Bind(wx.EVT_BUTTON, self.OnAccept)
		self.addButton.Bind(wx.EVT_BUTTON, self.OnOpen)
		self.removeButton.Bind(wx.EVT_BUTTON, self.OnRemoveItem)
		self.exitButton.Bind(wx.EVT_BUTTON, self.OnExit)

		# Set the sizer size and position
		panel.SetSizer(mainSizer)
		self.SetAutoLayout(1)
		mainSizer.Fit(self)

		self.isReady() # Initialize the program
		self.Show() # Start the main window (frame)

	# The event handlers

	def OnAccept(self, e):
		""" Commits the changes """

		# Check to see if there are any folders to add
		if self.libPathsList.GetCount() == 0:
			with wx.MessageDialog(self, 'Cannot proceed because there are no folders to add. Please add folders befor clicking accept.', 'Alert', wx.OK) as dlg:
				dlg.ShowModal()
			return

		info_t = collections.namedtuple( "info_t", ( "key", "value" ) )

		self.backup(self.vdfFile) # We are about to make changes to an important file. Back it up!

		# Add the library folders back to the library info
		for i, folder in enumerate(self.libPathsList.GetStrings()):
			self.libInfo["LibraryFolders"].append(info_t(key=i+1, value=folder.replace("\\", "\\\\")))

		with open(self.vdfFile, 'w') as outFile:
			for parent in self.libInfo:
				outFile.write("\"{}\"\n".format(parent))
				outFile.write("{\n")
				for i, info in enumerate(self.libInfo[parent]):
					outFile.write("\t\"{}\"\t\t\"{}\"\n".format(info.key, info.value))
					if parent == "LibraryFolders":
						# Remove each folder from the libInfo list again incase the user wants to change a folder.
						try:
							folder_id = int(info.key)
							self.libInfo[parent].pop(i)
						except:
							pass
				outFile.write("}\n")

		# Show a success message
			with wx.MessageDialog(self, 'The library folders were successfully added.', 'Alert', wx.OK) as dlg:
				dlg.ShowModal()

	def OnOpen(self, e):
		""" Opens a directory dialog for selecting a folder and adds the folder to the list """

		with wx.DirDialog(self, 'Choose A Folder', self.steamPath, wx.DD_DEFAULT_STYLE) as dlg:
			if dlg.ShowModal() == wx.ID_OK:
				self.libPathsList.Append(dlg.GetPath())

	def OnRemoveItem(self, e):
		""" Removes a folder from the list """

		# Check to see if there are any folders to remove. If not, throw an alert.
		if self.libPathsList.GetCount() <= 0:
			with wx.MessageDialog(self, 'Cannot proceed because there are no folders to remove.', 'Alert', wx.OK | wx.ICON_WARNING) as dlg:
				dlg.ShowModal()
			return

		# Check to see if a folder has been selected. If not, throw alert.
		if self.libPathsList.GetSelection():
			with wx.MessageDialog(self, 'Cannot proceed because you have not selected a folder to remove.', 'Alert', wx.OK) as dlg:
				dlg.ShowModal()
			return

		if self.libPathsList.GetSelection() >= 0:
			self.libPathsList.Delete(self.libPathsList.GetSelection())

	def OnExit(self, e):
		self.Close(True) # Close the frame
		exit(0)

app = wx.App(False) # Creates a new app and does not redirect stdout or stderr
frame = Window(None, 'Steam Library Setup Tool') # A frame is a top level window
app.MainLoop()