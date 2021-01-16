import traceback
import sys
import wx
from wx.adv import Sound
from time import sleep, time


class Runner():
    def __init__(self, stackView, sb=None):
        self.stackView = stackView
        self.locals = {}
        self.statusBar = sb
        self.globals = None

        self.keyCodeStringMap = {
            wx.WXK_RETURN:"Return",
            wx.WXK_NUMPAD_ENTER:"Enter",
            wx.WXK_TAB:"Tab",
            wx.WXK_SPACE:"Space",
            wx.WXK_NUMPAD_SPACE:"Space",
            wx.WXK_NUMPAD_TAB:"Tab",
            wx.WXK_ESCAPE:"Escape",
            wx.WXK_LEFT:"Left",
            wx.WXK_RIGHT:"Right",
            wx.WXK_UP:"Up",
            wx.WXK_DOWN:"Down",
            wx.WXK_SHIFT: "Shift",
            wx.WXK_ALT: "Alt",
            wx.WXK_CONTROL: "Control",
        }
        if wx.GetOsVersion()[0] == wx.OS_MAC_OSX_DARWIN:
            self.keyCodeStringMap[wx.WXK_ALT] = "Option"
            self.keyCodeStringMap[wx.WXK_CONTROL] = "Command"
            self.keyCodeStringMap[wx.WXK_RAW_CONTROL] = "Control"

    def SetupForCurrentCard(self):
        self.globals = {}
        self.globals["card"] = self.stackView.uiCard.model
        self.globals["Wait"] = self.Wait
        self.globals["Time"] = self.Time
        self.globals["Alert"] = self.Alert
        self.globals["Ask"] = self.Ask
        self.globals["GotoCard"] = self.GotoCard
        self.globals["GotoNextCard"] = self.GotoNextCard
        self.globals["GotoPreviousCard"] = self.GotoPreviousCard
        self.globals["GotoCardNumber"] = self.GotoCardNumber
        self.globals["PlaySound"] = self.PlaySound
        self.globals["StopSound"] = self.StopSound
        self.globals["BroadcastMessage"] = self.BroadcastMessage
        for ui in self.stackView.uiViews:
            self.globals[ui.model.GetProperty("name")] = ui.model

    def RunHandler(self, uiModel, handlerName, event, message=None):
        if not self.globals:
            self.SetupForCurrentCard()

        handlerStr = uiModel.handlers[handlerName]

        error_class = None
        line_number = None
        detail = None

        noValue = ["no value"]
        oldLocals = {}

        if "self" in self.locals:
            oldLocals["self"] = self.locals["self"]
        else:
            oldLocals["self"] = noValue
        self.locals["self"] = uiModel

        if message:
            if "message" in self.locals:
                oldLocals["message"] = self.locals["message"]
            else:
                oldLocals["message"] = noValue
            self.locals["message"] = message

        if event and handlerName.startswith("OnMouse"):
            mouseX, mouseY = self.stackView.ScreenToClient(event.GetEventObject().ClientToScreen(event.GetPosition()))
            if "mouseX" in self.locals:
                oldLocals["mouseX"] = self.locals["mouseX"]
            else:
                oldLocals["mouseX"] = noValue
            self.locals["mouseX"] = mouseX
            if "mouseY" in self.locals:
                oldLocals["mouseY"] = self.locals["mouseY"]
            else:
                oldLocals["mouseY"] = noValue
            self.locals["mouseY"] = mouseY

        if event and handlerName.startswith("OnKey"):
            code = event.GetKeyCode()
            if "key" in self.locals:
                oldLocals["key"] = self.locals["key"]
            else:
                oldLocals["key"] = noValue
            if code in self.keyCodeStringMap:
                self.locals["key"] = self.keyCodeStringMap[code]
            elif event.GetUnicodeKey() != wx.WXK_NONE:
                self.locals["key"] = chr(event.GetUnicodeKey())
            else:
                for k,v in oldLocals.items():
                    if v == noValue:
                        self.locals.pop(k)
                    else:
                        self.locals[k] = v
                return

        try:
            exec(handlerStr, self.globals, self.locals)
        except SyntaxError as err:
            error_class = err.__class__.__name__
            detail = err.args[0]
            line_number = err.lineno
        except Exception as err:
            error_class = err.__class__.__name__
            detail = err.args[0]
            cl, exc, tb = sys.exc_info()
            line_number = traceback.extract_tb(tb)[-1][1]

        for k, v in oldLocals.items():
            if v == noValue:
                self.locals.pop(k)
            else:
                self.locals[k] = v

        if error_class:
            msg = f"{error_class} in {uiModel.GetProperty('name')}.{handlerName}(), line {line_number}: {detail}"
            print(msg)
            if self.statusBar:
                self.statusBar.SetStatusText(msg)

    def SetFocus(self, model):
        uiView = self.stackView.GetUiViewByModel(model)
        if uiView:
            uiView.view.SetFocus()

    def StopRunning(self):
        Sound.Stop()

    def BroadcastMessage(self, message):
        self.RunHandler(self.stackView.uiCard.model, "OnMessage", None, message)
        for ui in self.stackView.uiViews:
            self.RunHandler(ui.model, "OnMessage", None, message)

    def GotoCard(self, cardName):
        index = None
        for m in self.stackView.stackModel.cardModels:
            if m.GetProperty("name") == cardName:
                index = self.stackView.stackModel.cardModels.index(m)
        if index is not None:
            self.stackView.LoadCardAtIndex(index)

    def GotoCardNumber(self, cardIndex):
        if cardIndex > 0 and cardIndex <= len(self.stackView.stackModel.cardModels):
            self.stackView.LoadCardAtIndex(cardIndex-1)

    def GotoNextCard(self):
        cardIndex = self.stackView.cardIndex + 1
        if cardIndex >= len(self.stackView.stackModel.cardModels): cardIndex = 0
        self.stackView.LoadCardAtIndex(cardIndex)

    def GotoPreviousCard(self):
        cardIndex = self.stackView.cardIndex - 1
        if cardIndex < 0: cardIndex = len(self.stackView.stackModel.cardModels) - 1
        self.stackView.LoadCardAtIndex(cardIndex)

    def Wait(self, delay):
        self.stackView.RefreshNow()
        sleep(delay)

    def Time(self):
        return time()

    def Alert(self, title, message=""):
        self.stackView.RefreshNow()
        wx.MessageDialog(None, str(message), str(title), wx.OK).ShowModal()

    def Ask(self, title, message=""):
        self.stackView.RefreshNow()
        r = wx.MessageDialog(None, str(message), str(title), wx.YES_NO).ShowModal()
        return (r == wx.ID_YES)

    def PlaySound(self, filepath):
        Sound.PlaySound(filepath)

    def StopSound(self):
        Sound.Stop()
