import subprocess
import datetime
import random
import thread
import pygame
#import ELM327
import Visual
import Button
import Gadgit
import Plot
import Config
import Select
import Confirm
import Display
import PDF



DISPLAY_PERIOD = 100
TIMER_PERIOD = 500


# Start value for pygame user events.
EVENT_TIMER = pygame.USEREVENT + 1

# Lock to prevent ELM327 communications occuring when an existing one still running.
LockELM327 = thread.allocate_lock()

# Lock to prevent multiple aquisition threads of execution.
LockAquisition = thread.allocate_lock()

# List of visual class instances to be flashed.
FlashVisuals = {}

#  /***************************************/
# /* Create application class instances. */
#/***************************************/
ThisELM327 = ELM327.ELM327()
ThisDisplay = Display.Display()
ThisPDF = PDF.PDF()



#/******************************************************/
#/* Display visual instances in their current Z order. */
#/******************************************************/
def DebugDisplayZOrder():
	Count = 0
	for ThisVisual in Visual.VisualZOrder:
		Count += 1
		print(str(Count) + " " + ThisVisual.GetName() + " " + str(ThisVisual))



#/************************************************/
#/* Apply the application configuration options. */
#/************************************************/
def ApplyConfig():
	Config.LoadConfig()
	ELM327.DEBUG = Config.ConfigValues["Debug"]
	ELM327.SERIAL_PORT_NAME = Config.ConfigValues["SerialPort"]
	ThisDisplay.DEBUG = Config.ConfigValues["Debug"]
	ThisELM327.LoadVehicle(Config.ConfigValues["Vehicle"])
	Visual.VisualZOrder[0].SetFont(Config.ConfigValues["FontName"])



#/******************************************/
#/* Print OBDII report on default printer. */
#/******************************************/
def PrintPdfReport():
	Result =  ""

	# Save PDF Report.
	Result = SavePdfReport("SAVE/PRINT.PDF")
	# Send PDF report to the default printer.
	try:
		subprocess.call("lpr SAVE/PRINT.PDF")
	except Exception as Catch:
		Result = str(Catch)

	return Result



#/************************************/
#/* Save OBDII report as a PDF file. */
#/************************************/
def SavePdfReport(FileName):
	ThisDisplay.Buttons["BUSY"].SetVisible(True)
	ThisDisplay.Buttons["BUSY"].SetDown(True)
	ThisDisplay.Display()
	try:
		# Get OBDII vehicle data.
		if LockELM327.acquire(0):
			VehicleData(ThisDisplay)
		# Get OBDII trouble data.
		if LockELM327.acquire(0):
			TroubleInfo(ThisDisplay)
		# Get OBDII data frame.
		if LockELM327.acquire(0):
			FrameData(ThisDisplay)
		# Get OBDII freeze frame.
		if LockELM327.acquire(0):
			FreezeFrameData(ThisDisplay)
		# Add data to the PDF report.
		Now = datetime.datetime.now()
		NowTime = Now.strftime("%H:%M")
		NowDate = Now.strftime("%Y-%m-%d")
		PdfData = [
			["OBDII VEHICLE INFORMATION", "PiOBDII|" + NowDate + " " + NowTime + "\n\n" + ThisDisplay.VehicleInfo["INFO"].GetText()],
			["OBDII TROUBLE INFORMATION", ThisDisplay.TroubleInfo["INFO"].GetText()],
			["OBDII DATA FREEZE FRAMES", ThisDisplay.FreezeFrameData["INFO"].GetText()],
			["OBDII DATA FRAME", ThisDisplay.FrameData["INFO"].GetText()],
			["ELM327 INFORMATION", ThisELM327.GetInfo()],
		]
		ThisPDF.CreateReport(FileName, "FreeMono", PdfData)
	except Exception as Catch:
		FileName = str(Catch)
	ThisDisplay.Buttons["BUSY"].SetDown(False)
	ThisDisplay.Buttons["BUSY"].SetVisible(False)

	return FileName



#/***************************************************/
#/* Perform a connection to the CAN BUS of the ECU. */
#/***************************************************/
def ConnectELM327(ThisDisplay):
	# Stop flashing MIL light before attempting a new connection.
	FlashVisuals.pop("MIL", None)
	ThisDisplay.Buttons["MIL"].SetDown(False)
	# Flash connect button during connection attempt.
	FlashVisuals["CONNECT"] = ThisDisplay.ELM327Info["CONNECT"]
	try:
		# Notify the user a connection attempt is taking place.
		ThisDisplay.SetVisualText(ThisDisplay.ELM327Info, "INFO", "CONNECTING TO CAN BUS FOR OBDII COMMUNICATION...\n", False)
		# Connect to the CAN BUS of the ECU.
		Result = ThisELM327.Connect()
		# Display issues initializing the ELM327 device.
		ThisDisplay.SetVisualText(ThisDisplay.ELM327Info, "INFO", ThisELM327.GetInitResult(), False)
		# Notify the user of any failures.
		if Result == ELM327.CONNECT_ELM327_FAIL:
			ThisDisplay.SetVisualText(ThisDisplay.ELM327Info, "INFO", "FAILED TO CONNECT TO ELM327 DEVICE.\n", True)
		elif Result == ELM327.CONNECT_CAN_BUS_FAIL:
			ThisDisplay.SetVisualText(ThisDisplay.ELM327Info, "INFO", "FAILED TO CONNECT TO CAN BUS.\n", True)
		else:
			# Display ELM327 information.
			ThisDisplay.SetVisualText(ThisDisplay.ELM327Info, "INFO", ThisELM327.GetInfo(), True)
	except Exception as Catch:
		print(str(Catch))
	# Stop flashing connect button after connection attempt.
	FlashVisuals.pop("CONNECT", None)
	ThisDisplay.ELM327Info["CONNECT"].SetDown(False)
	# Allow another ELM327 communication now this one is complete.
	LockELM327.release()
	# Check for MIL status after connection attempt.
	if ThisELM327.GetMilOn() == True:
		FlashVisuals["MIL"] = ThisDisplay.Buttons["MIL"]
	# Get a list of all valid PIDs the connected ECU supports.
	ValidPIDs = ThisELM327.GetValidPIDs()
	# Resume the state of the meters tab where last saved.
	ThisDisplay.LoadMetersTab(ValidPIDs)
	# Load the config for the plot series.
	ThisDisplay.Plots["PLOT"].LoadSeriesConfig(ValidPIDs)



#/**********************************************/
#/* Get a frame of all valid PIDs for Mode 01. */
#/**********************************************/
def FrameData(ThisDisplay):
	try:
		# Get a list of all valid PIDs the connected ECU supports.
		ValidPIDs = ThisELM327.GetValidPIDs()
		# Get the information available for each of the supported PIDs.
		ThisDisplay.SetVisualText(ThisDisplay.FrameData, "INFO", "", False)
		for PID in sorted(ValidPIDs):
			if ValidPIDs[PID][ELM327.FIELD_PID_DESCRIPTION] != '!':
				# Display the information returned for the current PID.
				if PID[1] == '1':
					PidData = ThisELM327.DoPID(PID)
					ThisDisplay.SetVisualText(ThisDisplay.FrameData, "INFO", "[" + PID + "] " + ValidPIDs[PID] + "\n", True, PidData)
	except Exception as Catch:
		print(str(Catch))
	# Allow another ELM327 communication now this one is complete.
	LockELM327.release()



#/*****************************************************/
#/* Get a freeze frame of all valid PIDs for Mode 02. */
#/*****************************************************/
def FreezeFrameData(ThisDisplay):
	try:
		for FreezeIndex in range(ThisELM327.GetFreezeFrameCount()):
			# Get a list of all valid PIDs the connected ECU supports.
			ValidPIDs = ThisELM327.GetValidPIDs(FreezeIndex)
			# Get the information available for each of the supported PIDs.
			ThisDisplay.SetVisualText(ThisDisplay.FreezeFrameData, "INFO", "", False)
			for PID in sorted(ValidPIDs):
				PidData = ThisELM327.DoPID(PID[:4], FreezeIndex)
				ThisDisplay.SetVisualText(ThisDisplay.FreezeFrameData, "INFO", "[" + PID + "] " + ValidPIDs[PID] + "\n", True, PidData)
	except Exception as Catch:
		print(str(Catch))
	# Allow another ELM327 communication now this one is complete.
	LockELM327.release()



#/**********************************************/
#/* Get a frame of all valid PIDs for Mode 09. */
#/**********************************************/
def VehicleData(ThisDisplay):
	try:
		# Get a list of all valid PIDs the connected ECU supports.
		ValidPIDs = ThisELM327.GetValidPIDs()
		# Get the information available for each of the supported PIDs.
		ThisDisplay.SetVisualText(ThisDisplay.VehicleInfo, "INFO", "", False)
		for PID in sorted(ValidPIDs):
			if ValidPIDs[PID][ELM327.FIELD_PID_DESCRIPTION] != '!':
				# Display the information returned for the current PID.
				if PID[1] == '9':
					PidData = ThisELM327.DoPID(PID)
					ThisDisplay.SetVisualText(ThisDisplay.VehicleInfo, "INFO", "[" + PID + "] " + ValidPIDs[PID] + "\n", True, PidData)
	except Exception as Catch:
		print(str(Catch))
	# Allow another ELM327 communication now this one is complete.
	LockELM327.release()



#/****************************************/
#/* Get all trouble related information. */
#/****************************************/
def TroubleInfo(ThisDisplay):
	try:
		# Get a list of all valid PIDs the connected ECU supports.
		ValidPIDs = ThisELM327.GetValidPIDs()
		# Display test information and MIL light status.
		PidData = sorted(ThisELM327.DoPID("0101"))
		ThisDisplay.SetVisualText(ThisDisplay.TroubleInfo, "INFO", "[0101] " + ValidPIDs["0101"] + "\n", False, PidData)

		# Display all stored trouble codes and descriptions.
		TroubleCodes = ThisELM327.DoPID("03")
		ThisDisplay.SetVisualText(ThisDisplay.TroubleInfo, "INFO", "\nSTORED TROUBLE CODES: [" + str(len(TroubleCodes)) + "]\n", True)
		if TroubleCodes != ELM327.STRING_ERROR:
			for TroubleCode in sorted(TroubleCodes):
				ThisDisplay.SetVisualText(ThisDisplay.TroubleInfo, "INFO", str(TroubleCode) + " " + str(TroubleCodes[TroubleCode]) + "\n", True)

		# Display all pending trouble codes and descriptions.
		TroubleCodes = ThisELM327.DoPID("07")
		ThisDisplay.SetVisualText(ThisDisplay.TroubleInfo, "INFO", "\nPENDING TROUBLE CODES [" + str(len(TroubleCodes)) + "]:\n", True)
		if TroubleCodes != ELM327.STRING_ERROR:
			for TroubleCode in sorted(TroubleCodes):
				ThisDisplay.SetVisualText(ThisDisplay.TroubleInfo, "INFO", str(TroubleCode) + " " + str(TroubleCodes[TroubleCode]) + "\n", True)
	except Exception as Catch:
		print(str(Catch))
	# Allow another ELM327 communication now this one is complete.
	LockELM327.release()



#/*********************************************/
#/* Clear all trouble codes and related data. */
#/*********************************************/
def ClearTroubleInfo(ThisDisplay):
	try:
		TroubleCodes = ThisELM327.DoPID("04")
	except Exception as Catch:
		print(str(Catch))
	# Allow another ELM327 communication now this one is complete.
	LockELM327.release()
	if LockELM327.acquire(0):
		thread.start_new_thread(TroubleInfo, (ThisDisplay, ))



#/*********************************************************/
#/* Update the data for the created gadgits from the ECU. */
#/*********************************************************/
def MeterData(ThisDisplay):
	ThisDisplay.Buttons["BUSY"].SetVisible(True)
	FlashVisuals["BUSY"] = ThisDisplay.Buttons["BUSY"]
	try:
		# Get the information available for each of the meter related PIDs.
		for ThisGadgit in ThisDisplay.Meters:
			if type(ThisDisplay.Meters[ThisGadgit]) is Gadgit.Gadgit:
				PID = ThisDisplay.Meters[ThisGadgit].GetPID()
				if PID != "":
					# Store the information returned for the current PID on the related meter.
					PidData = ThisELM327.DoPID(PID)
					ThisDisplay.Meters[ThisGadgit].SetData(PidData)
	except Exception as Catch:
		print(str(Catch))
	# Allow another ELM327 communication now this one is complete.
	LockELM327.release()
	FlashVisuals.pop("BUSY", None)
	ThisDisplay.Buttons["BUSY"].SetVisible(False)



#/*********************************************************/
#/* Update the data for the created gadgits from the ECU. */
#/*********************************************************/
def PlotData(ThisDisplay):
	ThisDisplay.Buttons["BUSY"].SetVisible(True)
	FlashVisuals["BUSY"] = ThisDisplay.Buttons["BUSY"]
	try:
		# Get the information available for each of the plot related PIDs.
		for Index in range(Plot.PLOT_COUNT):
			if ThisDisplay.Plots["PLOT"].IsDataEnd(Index) == False:
				PID = ThisDisplay.Plots["PLOT"].GetPID(Index)
				if PID != "":
					# Plot the information returned for the current PID.
					PidData = ThisELM327.DoPID(PID)
					ThisDisplay.Plots["PLOT"].SetData(Index, PidData)
	except Exception as Catch:
		print(str(Catch))
	# Allow another ELM327 communication now this one is complete.
	LockELM327.release()
	FlashVisuals.pop("BUSY", None)
	ThisDisplay.Buttons["BUSY"].SetVisible(False)



#/*********************************************************/
#/* Aquire data as fast as possible for plots and meters. */
#/*********************************************************/
def AquisitionLoop(ThisDisplay):
	try:
		while (ThisDisplay.Meters["GO_STOP"].GetDown() == True or ThisDisplay.Plots["GO_STOP"].GetDown() == True):
			# Update the gadgit data from the ECU.
			if ThisDisplay.CurrentTab == ThisDisplay.Meters and ThisDisplay.Meters["LOCK"].GetDown() == True and ThisDisplay.Meters["GO_STOP"].GetDown() == True:
				if LockELM327.acquire(0):
					thread.start_new_thread(MeterData, (ThisDisplay, ))
			# Update the plot data from the ECU.
			if ThisDisplay.CurrentTab == ThisDisplay.Plots and ThisDisplay.Plots["GO_STOP"].GetDown() == True:
				if LockELM327.acquire(0):
					thread.start_new_thread(PlotData, (ThisDisplay, ))
	except Exception as Catch:
		print(str(Catch))
	# Allow this function to be called again if required.
	LockAquisition.release()




# Set the configuration before start.
ApplyConfig()

# Create a timer for updating the displayed time/date and updating gadgit data from the ECU.
pygame.time.set_timer(EVENT_TIMER, TIMER_PERIOD)

# Aquire a lock for use when communicating with the ELM327 device.
if LockELM327.acquire(0):
	thread.start_new_thread(ConnectELM327, (ThisDisplay, ))

# Application message loop.
ExitFlag = False
while ExitFlag == False:
	pygame.time.wait(DISPLAY_PERIOD)

	# Process pygame events.
	for ThisEvent in pygame.event.get():
		# If pygame says quit, finish the application.
		if ThisEvent.type == pygame.QUIT:
			ExitFlag = True
		elif ThisEvent.type == pygame.KEYDOWN:
			KeysPressed = pygame.key.get_pressed()
			# If the ESC key is pressed, finish the application.
			if KeysPressed[pygame.K_ESCAPE]:
				ExitFlag = True
		elif ThisEvent.type == EVENT_TIMER:
			try:
				# Update the displayed date and time.
				Now = datetime.datetime.now()
				NowTime = Now.strftime("%H:%M")
				NowDate = Now.strftime("%Y-%m-%d")
				ThisDisplay.SetVisualText(ThisDisplay.CurrentTab, "TIME", NowTime)
				ThisDisplay.SetVisualText(ThisDisplay.CurrentTab, "DATE", NowDate)

				# Unhighlight pressed buttons which are not latch or toggle.
				for ThisVisual in Visual.VisualZOrder:
					if ThisVisual.GetName() not in FlashVisuals and ThisVisual.GetPressType() == Visual.PRESS_DOWN:
						ThisVisual.SetDown(False)

				# Flash visual instances flagged to be flashed.
				for ThisVisual in FlashVisuals:
					if FlashVisuals[ThisVisual].GetDown() == False:
						FlashVisuals[ThisVisual].SetDown(True)
					else:
						FlashVisuals[ThisVisual].SetDown(False)
			except Exception as Catch:
				print(str(Catch))
		# Only process the following events if the ELM327 device is currently communicating.
		elif LockELM327.locked() == True:
			if ThisEvent.type == pygame.MOUSEBUTTONDOWN:
				# Allow GO/STOP button to be toggled while ELM327 communications are occuring.
				if ThisDisplay.CurrentTab == ThisDisplay.Meters:
					ThisDisplay.Meters["GO_STOP"].IsEvent(Visual.EVENT_MOUSE_DOWN, ThisEvent.pos[0], ThisEvent.pos[1], ThisEvent.button)
				elif ThisDisplay.CurrentTab == ThisDisplay.Plots:
					ThisDisplay.Plots["GO_STOP"].IsEvent(Visual.EVENT_MOUSE_DOWN, ThisEvent.pos[0], ThisEvent.pos[1], ThisEvent.button)

		# Only process the following events if the ELM327 device is not currently communicating.
		elif LockELM327.locked() == False:
			if ThisEvent.type == pygame.MOUSEBUTTONDOWN:
				# Pass button down events to all buttons and gadgits.
				ButtonGadgit = ThisDisplay.IsEvent(Visual.EVENT_MOUSE_DOWN, ThisEvent.pos[0], ThisEvent.pos[1], ThisEvent.button)
				if Config.ConfigValues["Debug"] == "ON":
					print(str(ButtonGadgit))
				if ButtonGadgit != False:
					# If exit button is pressed, finish the application.
					if ButtonGadgit["BUTTON"] == "EXIT":
						# Display a confirmation to exit the application.
						ThisDisplay.CurrentTab["CONFIRM"] = Confirm.Confirm(ThisDisplay.ThisSurface, "CONFIRM_EXIT", "Exit the application?")
					# If confirm dialog button yes is pressed, close the dialog.
					elif ButtonGadgit["BUTTON"] == "YES":
						ThisDisplay.CurrentTab.pop("CONFIRM", None)
						if ButtonGadgit["GADGIT"] == "CONFIRM_EXIT":
							ExitFlag = True
						elif ButtonGadgit["GADGIT"] == "CONFIRM_CLEAR_ECU":
							if LockELM327.acquire(0):
								thread.start_new_thread(ClearTroubleInfo, (ThisDisplay, ))
					# If confirm dialog button no is pressed, close the dialog.
					elif ButtonGadgit["BUTTON"] == "NO":
						ThisDisplay.CurrentTab.pop("CONFIRM", None)
					# If select dialog selection is made, close the dialog.
					elif "SELECTED" in ButtonGadgit:
						ThisDisplay.CurrentTab.pop("SELECT", None)
						if ButtonGadgit["SELECTED"] != False:
							SelectLines = SelectText.split('\n')
							SelectedLine = SelectLines[ButtonGadgit["SELECTED"] - 1]
							if ButtonGadgit["GADGIT"] == "SELECT_PID":
								ThisPID = SelectedLine[SelectedLine.find("[") + 1:SelectedLine.find("]")]
								# Get a list of all valid PIDs the connected ECU supports.
								ValidPIDs = ThisELM327.GetValidPIDs()
								if ThisPID in ValidPIDs:
									if SelectGadgit[:5] != "PLOT_":
										ThisDisplay.Meters[SelectGadgit].SetPID(ThisPID, ValidPIDs[ThisPID])
									else:
										ThisDisplay.Plots["PLOT"].SetPID(int(SelectGadgit[5]) - 1, ThisPID, ValidPIDs[ThisPID])
								else:
									if SelectGadgit[:5] != "PLOT_":
										ThisDisplay.Meters[SelectGadgit].SetPID("", "")
									else:
										ThisDisplay.Plots["PLOT"].SetPID(int(SelectGadgit[5]) - 1, "", "")
							elif ButtonGadgit["GADGIT"] == "SELECT_FONT_NAME":
								Config.ConfigValues["FontName"] = SelectedLine
							elif ButtonGadgit["GADGIT"] == "SELECT_SERIAL_PORT_NAME":
								Config.ConfigValues["SerialPort"] = SelectedLine
							elif ButtonGadgit["GADGIT"] == "SELECT_VEHICLE_NAME":
								Config.ConfigValues["Vehicle"] = SelectedLine
					# If print button is pressed.
					elif ButtonGadgit["BUTTON"] == "PRINT":
						# Print PDF Report.
						Result = PrintPdfReport()
						# Display print report message.
						ThisDisplay.CurrentTab["CONFIRM"] = Confirm.Confirm(ThisDisplay.ThisSurface, "CONFIRM_PRINT", "OBDII Report Sent To Default Printer\n" + Result, ThisDisplay.GetDisplayWidth()/1.5, True)
					# If save button is pressed.
					elif ButtonGadgit["BUTTON"] == "SAVE":
						# Get the date and time for the report filename.
						Now = datetime.datetime.now()
						FileName = "SAVE/"
						FileName += Now.strftime("%Y-%m-%d_%H-%M-%S_")
						# Get Vehicle VIN for report filename.
						FileName += ThisELM327.DoPID("0902").replace(' ', '') + ".pdf"
						# Save PDF Report.
						Result = SavePdfReport(FileName)
						# Display PDF saved message.
						ThisDisplay.CurrentTab["CONFIRM"] = Confirm.Confirm(ThisDisplay.ThisSurface, "CONFIRM_PDF", "OBDII Report Saved:\n" + Result, ThisDisplay.GetDisplayWidth()/1.5, True)
					# If reset plot button is pressed.
					elif ButtonGadgit["BUTTON"] == "RESET":
						ThisDisplay.Plots["PLOT"].ClearData()
					# If configure button is pressed.
					elif ButtonGadgit["BUTTON"] == "CONFIG":
						# Display configuration dialog.
						ThisDisplay.CurrentTab["CONFIGURE"] = Config.Config(ThisDisplay.ThisSurface, "CONFIGURE", "CONFIGURE")
					# If save config button is pressed.
					elif ButtonGadgit["BUTTON"] == "SAVE_CONFIG":
						ThisDisplay.CurrentTab.pop("CONFIGURE", None)
						ApplyConfig()
					elif ButtonGadgit["BUTTON"] == "SELECT_FONT":
						# Remember which gadgit the select is for.
						SelectGadgit = ButtonGadgit["GADGIT"]
						# Get a list of mono space font names.
						SelectText = ThisDisplay.CurrentTab["CONFIGURE"].GetFontNameList()
						# Display a font name selection dialog.
						ThisDisplay.CurrentTab["SELECT"] = Select.Select(ThisDisplay.ThisSurface, "SELECT_FONT_NAME", SelectText)
					elif ButtonGadgit["BUTTON"] == "SELECT_VEHICLE":
						# Remember which gadgit the select is for.
						SelectGadgit = ButtonGadgit["GADGIT"]
						# Get a list of vehicle trouble code file names.
						SelectText = ThisDisplay.CurrentTab["CONFIGURE"].GetVehicleNameList()
						# Display a font name selection dialog.
						ThisDisplay.CurrentTab["SELECT"] = Select.Select(ThisDisplay.ThisSurface, "SELECT_VEHICLE_NAME", SelectText)
					elif ButtonGadgit["BUTTON"] == "SELECT_SERIAL_PORT":
						# Remember which gadgit the select is for.
						SelectGadgit = ButtonGadgit["GADGIT"]
						# Get a list of vehicle trouble code file names.
						SelectText = ThisDisplay.CurrentTab["CONFIGURE"].GetSerialPortNameList()
						# Display a font name selection dialog.
						ThisDisplay.CurrentTab["SELECT"] = Select.Select(ThisDisplay.ThisSurface, "SELECT_SERIAL_PORT_NAME", SelectText)
					# If connect button is pressed, connect to the CAN BUS.
					elif ButtonGadgit["BUTTON"] == "CONNECT":
						if LockELM327.acquire(0):
							thread.start_new_thread(ConnectELM327, (ThisDisplay, ))
					# If select button is pressed, select a PID for the specific gadgit.
					elif ButtonGadgit["BUTTON"] == "SELECT" or ButtonGadgit["BUTTON"][:5] == "PLOT_":
						# Remember which gadgit the select is for.
						if ButtonGadgit["BUTTON"] == "SELECT":
							SelectGadgit = ButtonGadgit["GADGIT"]
						else:
							SelectGadgit = ButtonGadgit["BUTTON"]
						# Get a list of all valid PIDs the connected ECU supports.
						ValidPIDs = ThisELM327.GetValidPIDs()
						# Get the information available for each of the supported PIDs.
						SelectText = "NONE\n"
						for PID in sorted(ValidPIDs):
							if ValidPIDs[PID][ELM327.FIELD_PID_DESCRIPTION] != '!':
								PidDescription = ValidPIDs[PID].split("|")
								SelectText += "[" + PID + "] " + PidDescription[0] + "\n"
						# Display a PID selection dialog.
						ThisDisplay.CurrentTab["SELECT"] = Select.Select(ThisDisplay.ThisSurface, "SELECT_PID", SelectText)
					# If close button is pressed, close the relavent dialog.
					elif ButtonGadgit["BUTTON"] == "CLOSE":
						if ButtonGadgit["BUTTON"] == "SELECT":
							ThisDisplay.CurrentTab.pop("SELECT", None)
						elif ButtonGadgit["BUTTON"] == "CONFIGURE":
							ThisDisplay.CurrentTab.pop("CONFIGURE", None)
					# If vehicle button is pressed, get the vehicle data from the ECU.
					elif ButtonGadgit["BUTTON"] == "VEHICLE":
						if LockELM327.acquire(0):
							thread.start_new_thread(VehicleData, (ThisDisplay, ))
					# If trouble or refresh button is pressed, get the trobule related data from the ECU.
					elif ButtonGadgit["BUTTON"] == "TROUBLE" or ButtonGadgit["BUTTON"] == "MIL" or ButtonGadgit["BUTTON"] == "REFRESH":
						if LockELM327.acquire(0):
							thread.start_new_thread(TroubleInfo, (ThisDisplay, ))
							# Check for MIL status after reading trouble data.
							FlashVisuals.pop("MIL", None)
							ThisDisplay.Buttons["MIL"].SetDown(False)
							if ThisELM327.GetMilOn() == True:
								FlashVisuals["MIL"] = ThisDisplay.Buttons["MIL"]
					# If clear button is pressed, clear the trouble and related data on the ECU.
					elif ButtonGadgit["BUTTON"] == "CLEAR":
						# Display a confirmation to clear ECU trouble codes.
						ThisDisplay.CurrentTab["CONFIRM"] = Confirm.Confirm(ThisDisplay.ThisSurface, "CONFIRM_CLEAR_ECU", "Clear all trouble codes\nand related data\non the ECU?")
					# If freeze button is pressed.
					elif ButtonGadgit["BUTTON"] == "FREEZE" or ButtonGadgit["BUTTON"] == "RELOAD_FREEZE":
						if LockELM327.acquire(0):
							thread.start_new_thread(FreezeFrameData, (ThisDisplay, ))
					# If frame button is pressed, get a frame of data from the ECU.
					elif ButtonGadgit["BUTTON"] == "FRAME" or ButtonGadgit["BUTTON"] == "RELOAD":
						if LockELM327.acquire(0):
							thread.start_new_thread(FrameData, (ThisDisplay, ))
					# If add button is pressed, add a new gadgit to the meters tab.
					elif ButtonGadgit["BUTTON"] == "ADD":
						if ThisDisplay.CurrentTab == ThisDisplay.Meters:
							NewName = "{:X}".format(random.getrandbits(128))
							ThisDisplay.Meters[NewName] = Gadgit.Gadgit(ThisDisplay.ThisSurface, NewName, Visual.PRESS_NONE, 0, 2 * Visual.BUTTON_HEIGHT, ThisDisplay.GadgitWidth, ThisDisplay.GadgitHeight, "NEW")
					# If GO/STOP button is pressed, start data aquisition.
					elif ButtonGadgit["BUTTON"] == "GO_STOP":
						if ThisDisplay.CurrentTab == ThisDisplay.Meters or ThisDisplay.CurrentTab == ThisDisplay.Plots:
							if LockAquisition.acquire(0):
								thread.start_new_thread(AquisitionLoop, (ThisDisplay, ))
					# If add button is pressed, add a new gadgit to the meters tab.
					elif ButtonGadgit["BUTTON"] == "LOCK":
						if ThisDisplay.Meters["LOCK"].GetDown() == False:
							ThisDisplay.Meters["ADD"].SetVisible(True)
						else:
							ThisDisplay.Meters["ADD"].SetVisible(False)
						for ThisGadget in ThisDisplay.Meters:
							if type(ThisDisplay.Meters[ThisGadget]) is not str and type(ThisDisplay.Meters[ThisGadget]) is not Button.Button:
								for ThisButton in ThisDisplay.Meters[ThisGadget].Buttons:
									if ThisDisplay.Meters["LOCK"].GetDown() == False:
										ThisDisplay.Meters[ThisGadget].Buttons[ThisButton].SetVisible(True)
									else:
										ThisDisplay.Meters[ThisGadget].Buttons[ThisButton].SetVisible(False)
			elif ThisEvent.type == pygame.MOUSEBUTTONUP:
				# Pass button up events to all buttons and gadgits.
				ButtonGadgit = ThisDisplay.IsEvent(Visual.EVENT_MOUSE_UP, ThisEvent.pos[0], ThisEvent.pos[1], ThisEvent.button)
			elif ThisEvent.type == pygame.MOUSEMOTION:
				# When a button is down, pass movement events to all buttons and gadgits.
				if ThisEvent.buttons[0] > 0:
					ButtonGadgit = ThisDisplay.IsEvent(Visual.EVENT_MOUSE_MOVE, ThisEvent.pos[0], ThisEvent.pos[1], ThisEvent.buttons[0])
				else:
					ButtonGadgit = ThisDisplay.IsEvent(Visual.EVENT_MOUSE_HOVER, ThisEvent.pos[0], ThisEvent.pos[1], ThisEvent.buttons[0])

	# Update the display.
	ThisDisplay.Display()



# Save the current state of the meters tab to resume when next run.
ThisDisplay.SaveMetersTab()
# Save the config for the plot series.
ThisDisplay.Plots["PLOT"].SaveSeriesConfig()

# Terminate application.
pygame.time.set_timer(EVENT_TIMER, 0)
ThisDisplay.Close()
quit()

