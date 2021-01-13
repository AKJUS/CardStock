#!/usr/bin/python
# stackWindow.py

"""
This module contains the StackWindow class which is a window that you
can do simple drawings upon. and add Buttons and TextFields to.
"""


import wx
from wx.lib.docview import CommandProcessor, Command
import json
from stack import StackModel
from uiCard import UiCard, CardModel
from uiButton import UiButton
from uiTextField import UiTextField
from uiTextLabel import UiTextLabel
from uiImage import UiImage

# ----------------------------------------------------------------------

class StackWindow(wx.Window):
    menuColours = { 100 : 'White',
                    101 : 'Yellow',
                    102 : 'Red',
                    103 : 'Green',
                    104 : 'Blue',
                    105 : 'Purple',
                    106 : 'Brown',
                    107 : 'Aquamarine',
                    108 : 'Forest Green',
                    109 : 'Light Blue',
                    110 : 'Goldenrod',
                    111 : 'Cyan',
                    112 : 'Orange',
                    113 : 'Black',
                    114 : 'Dark Grey',
                    115 : 'Light Grey',
                    }
    maxThickness = 16

    def __init__(self, parent, ID, stackModel):
        wx.Window.__init__(self, parent, ID, style=wx.NO_FULL_REPAINT_ON_RESIZE|wx.WANTS_CHARS)
        self.SetBackgroundColour("WHITE")
        self.listeners = []
        self.designer = None
        self.isEditing = False
        self.command_processor = CommandProcessor()
        self.pos = wx.Point(0,0)
        self.isInDrawingMode = False
        self.showCardPending = False
        self.isDrawing = False
        self.thickness = 4
        self.curLine = []
        self.colour = None
        self.pen = None
        self.SetColour("Black")
        self.timer = None

        if not stackModel:
            stackModel = StackModel()
            stackModel.AddCardModel(CardModel())

        self.stackModel = stackModel
        self.selectedView = None
        self.uiViews = []
        self.cardIndex = None
        self.uiCard = UiCard(self, stackModel.cardModels[0])
        self.LoadCardAtIndex(0)

        self.uiCard.model.SetDirty(False)
        self.command_processor.ClearCommands()

        self.InitBuffer()
        self.UpdateCursor()

        # hook some mouse events
        self.Bind(wx.EVT_LEFT_DOWN, self.OnMouseDown)
        self.Bind(wx.EVT_LEFT_UP, self.OnMouseUp)
        # if editing:
        #     self.Bind(wx.EVT_RIGHT_UP, self.OnMouseRightUp)
        self.Bind(wx.EVT_MOTION, self.OnMouseMove)
        self.Bind(wx.EVT_KEY_DOWN, self.OnKeyDown)
        self.Bind(wx.EVT_KEY_UP, self.OnKeyUp)

        # the view resize event and idle events for managing the buffer
        self.Bind(wx.EVT_SIZE, self.OnSize)
        self.Bind(wx.EVT_IDLE, self.OnIdle)

        # and the refresh event
        self.Bind(wx.EVT_PAINT, self.OnPaint)

        # When the window is destroyed, clean up resources.
        self.Bind(wx.EVT_WINDOW_DESTROY, self.Cleanup)

    def Cleanup(self, evt):
        if evt.GetEventObject() == self:
            if hasattr(self, "menu"):
                self.menu.Destroy()
                del self.menu
            if self.timer:
                self.timer.Stop()

    def SetEditing(self, editing):
        self.isEditing = editing
        if not editing:
            self.SelectUiView(None)
            self.timer = wx.Timer(self)
            self.Bind(wx.EVT_TIMER, self.OnIdleTimer, self.timer)
            self.timer.Start(50)

    def UpdateCursor(self):
        self.SetCursor(wx.Cursor(wx.CURSOR_PENCIL if self.isInDrawingMode else wx.CURSOR_HAND))

    def OnIdleTimer(self, event):
        self.uiCard.OnIdle(event)

    def SetDrawingMode(self, drawMode):
        self.isInDrawingMode = drawMode
        self.UpdateCursor()

    def ClearAllViews(self):
        self.SelectUiView(None)
        for ui in self.uiViews.copy():
            if ui.model.type != "card":
                ui.model.RemovePropertyListener(self.OnPropertyChanged)
                self.uiViews.remove(ui)
                ui.DestroyView()

    def CreateViews(self, cardModel):
        self.uiCard.SetModel(cardModel)
        self.uiViews = []
        for m in cardModel.childModels:
            self.AddUiViewFromModel(m, canUndo=False)  # Don't allow undoing card loads

    def SetStackModel(self, model):
        self.ClearAllViews()
        self.stackModel = model
        self.cardIndex = None
        self.LoadCardAtIndex(0)
        self.command_processor.ClearCommands()
        self.stackModel.SetDirty(False)

    def LoadCardAtIndex(self, index):
        if index != self.cardIndex:
            if not self.isEditing and self.cardIndex is not None:
                oldCardModel = self.stackModel.cardModels[self.cardIndex]
                if oldCardModel.runner:
                    oldCardModel.runner.RunHandler(oldCardModel, "OnHideCard", None)
            self.cardIndex = index
            self.ClearAllViews()
            if index is not None:
                cardModel = self.stackModel.GetCardModel(index)
                self.CreateViews(cardModel)
                self.SelectUiView(self.uiCard)
                cardModel.AddPropertyListener(self.OnPropertyChanged)
                self.InitBuffer()
                if self.designer:
                    self.designer.UpdateCardList()
                self.showCardPending = True

    def SetDesigner(self, designer):
        self.designer = designer

    def InitBuffer(self):
        """Initialize the bitmap used for buffering the display."""
        size = self.GetClientSize()
        self.buffer = wx.Bitmap(max(1,size.width), max(1,size.height))
        dc = wx.BufferedDC(None, self.buffer)
        dc.SetBackground(wx.Brush(self.GetBackgroundColour()))
        dc.Clear()
        self.DrawShapes(dc)
        self.reInitBuffer = False

    def SetColour(self, colour):
        """Set a new colour and make a matching pen"""
        self.colour = colour
        self.pen = wx.Pen(self.colour, self.thickness, wx.PENSTYLE_SOLID)
        self.Notify()

    def SetThickness(self, num):
        """Set a new line thickness and make a matching pen"""
        self.thickness = num
        self.pen = wx.Pen(self.colour, self.thickness, wx.PENSTYLE_SOLID)
        self.Notify()

    def CopyView(self):
        clipData = wx.CustomDataObject("org.cardstock.models")
        list = [self.selectedView.model.GetData()]
        data = bytes(json.dumps(list).encode('utf8'))
        clipData.SetData(data)
        wx.TheClipboard.Open()
        wx.TheClipboard.SetData(clipData)
        wx.TheClipboard.Close()

    def CutView(self):
        if self.selectedView != self.uiCard:
            self.CopyView()
            v = self.selectedView
            command = RemoveUiViewCommand(True, "Cut", self, self.cardIndex, v.model)
            self.command_processor.Submit(command)

    def PasteView(self):
        if not wx.TheClipboard.IsOpened():  # may crash, otherwise
            if wx.TheClipboard.Open():
                if wx.TheClipboard.IsSupported(wx.DataFormat("org.cardstock.models")):
                    clipData = wx.CustomDataObject("org.cardstock.models")
                    if wx.TheClipboard.GetData(clipData):
                        rawdata = clipData.GetData()
                        list = json.loads(rawdata.tobytes().decode('utf8'))
                        uiView = None
                        for dict in list:
                            model = CardModel.ModelFromData(dict)
                            if model.type == "card":
                                for m in model.childModels:
                                    uiView = self.AddUiViewFromModel(m)
                            else:
                                uiView = self.AddUiViewFromModel(model)
                        if uiView:
                            self.SelectUiView(uiView)
                wx.TheClipboard.Close()

    def AddUiViewOfType(self, viewType):
        if viewType == "button":
            command = AddUiViewCommand(True, 'Add Button', self, self.cardIndex, "button")
        elif viewType == "textfield":
            command = AddUiViewCommand(True, 'Add TextField', self, self.cardIndex, "textfield")
        elif viewType == "textlabel":
            command = AddUiViewCommand(True, 'Add TextLabel', self, self.cardIndex, "textlabel")
        elif viewType == "image":
            command = AddUiViewCommand(True, 'Add Image', self, self.cardIndex, "image")

        self.command_processor.Submit(command)
        uiView = self.uiViews[-1]
        self.SelectUiView(uiView)
        return uiView

    def AddUiViewInternal(self, type, model=None):
        uiView = None
        if type == "button":
            uiView = UiButton(self, model)
        elif type == "textfield":
            uiView = UiTextField(self, model)
        elif type == "textlabel":
            uiView = UiTextLabel(self, model)
        elif type == "image":
            uiView = UiImage(self, model)

        if uiView:
            if not model:
                uiView.view.Center()
                uiView.model.SetProperty("position", uiView.view.GetPosition())
                uiView.model.SetProperty("size", uiView.view.GetSize())
            self.uiViews.append(uiView)
            if not uiView.model in self.uiCard.model.childModels:
                self.uiCard.model.AddChild(uiView.model)
            uiView.model.AddPropertyListener(self.OnPropertyChanged)
        return uiView

    def AddUiViewFromModel(self, model, canUndo=True):
        uiView = None

        if not model in self.uiCard.model.childModels:
            model.SetProperty("name", self.uiCard.model.DeduplicateNameInCard(model.GetProperty("name")))

        if model.GetType() == "button":
            command = AddUiViewCommand(True, 'Add Button', self, self.cardIndex, "button", model)
        elif model.GetType() == "textfield":
            command = AddUiViewCommand(True, 'Add TextField', self, self.cardIndex, "textfield", model)
        elif model.GetType() == "textlabel":
            command = AddUiViewCommand(True, 'Add TextLabel', self, self.cardIndex, "textlabel", model)
        elif model.GetType() == "image":
            command = AddUiViewCommand(True, 'Add Image', self, self.cardIndex, "image", model)

        if canUndo:
            self.command_processor.Submit(command)
        else:
            # Don't mess with the Undo queue when we're just building a pgae
            command.Do()

        uiView = self.uiViews[-1]
        return uiView

    def GetSelectedUiView(self):
        return self.selectedView

    def SelectUiView(self, view):
        if self.isEditing:
            if self.selectedView:
                self.selectedView.SetSelected(False)
            if view:
                view.SetSelected(True)
            self.selectedView = view
            if self.designer:
                self.designer.SetSelectedUiView(view)

    def OnPropertyChanged(self, model, key):
        uiView = self.GetUiViewByModel(model)
        if self.designer:
            self.designer.cPanel.UpdatedProperty(uiView, key)

    def UpdateSelectedUiView(self):
        if self.designer:
            self.designer.UpdateSelectedUiView()

    def GetUiViewByModel(self, model):
        for ui in self.uiViews:
            if ui.model == model:
                return ui
        return None

    def RemoveUiViewByModel(self, viewModel):
        for ui in self.uiViews.copy():
            if ui.model == viewModel:
                if self.selectedView == ui:
                    self.SelectUiView(self.uiCard)
                ui.model.RemovePropertyListener(self.OnPropertyChanged)
                self.uiViews.remove(ui)
                self.uiCard.model.RemoveChild(ui.model)
                ui.DestroyView()
                return

    def ReorderSelectedView(self, direction):
        if self.selectedView and self.selectedView != self.uiCard:
            currentIndex = self.uiCard.model.childModels.index(self.selectedView.model)
            newIndex = None
            if direction == "front": newIndex = 0
            elif direction == "fwd": newIndex = currentIndex+1
            elif direction == "back": newIndex = currentIndex-1
            elif direction == "end": newIndex = len(self.uiCard.model.childModels)-1

            if newIndex < 0: newIndex = 0
            if newIndex >= len(self.uiCard.model.childModels): newIndex = len(self.uiCard.model.childModels)-1

            if newIndex and newIndex != currentIndex:
                self.uiCard.model.childModels.insert(newIndex, self.uiCard.model.childModels.pop(currentIndex))
                self.LoadCardAtIndex(self.cardIndex)

    def ReorderCurrentCard(self, direction):
        currentIndex = self.cardIndex
        newIndex = None
        if direction == "fwd": newIndex = currentIndex + 1
        elif direction == "back": newIndex = currentIndex - 1

        if newIndex < 0: newIndex = 0
        if newIndex >= len(self.stackModel.cardModels): newIndex = len(self.stackModel.cardModels) - 1

        if newIndex and newIndex != currentIndex:
            self.stackModel.cardModels.insert(newIndex, self.stackModel.cardModels[currentIndex])
            self.cardIndex = newIndex
            self.UpdateCardChooser()

    def UpdateCardChooser(self):
        pass

    def AddCard(self):
        newCard = CardModel()
        newCard.SetProperty("name", newCard.DeduplicateName("card_1",
                                                            [m.GetProperty("name") for m in self.stackModel.cardModels]))
        command = AddUiViewCommand(True, "Add Card", self, self.cardIndex+1, "card", newCard)
        self.command_processor.Submit(command)

    def DuplicateCard(self):
        newCard = CardModel()
        newCard.SetData(self.stackModel.cardModels[self.cardIndex].GetData())
        newCard.SetProperty("name", newCard.DeduplicateName(newCard.GetProperty("name"),
                                                            [m.GetProperty("name") for m in self.stackModel.cardModels]))
        command = AddUiViewCommand(True, "Duplicate Card", self, self.cardIndex+1, "card", newCard)
        self.command_processor.Submit(command)

    def RemoveCard(self):
        index = self.cardIndex
        if len(self.stackModel.cardModels) > 1:
            command = RemoveUiViewCommand(True, "Add Card", self, index, self.stackModel.cardModels[index])
            self.command_processor.Submit(command)

    def OnMouseDown(self, event):
        """called when the left mouse button is pressed"""
        if self.isEditing:
            if self.isInDrawingMode:
                self.curLine = []
                self.pos = event.GetPosition()
                coords = (self.pos.x, self.pos.y)
                self.curLine.append(coords)
                self.isDrawing = True
                self.CaptureMouse()
            else:
                self.SelectUiView(self.uiCard)
        else:
            event.Skip()

    def OnMouseMove(self, event):
        """
        Called when the mouse is in motion.  If the left button is
        dragging then draw a line from the last event position to the
        current one.  Save the coordinants for redraws.
        """
        if self.isEditing:
            if self.isDrawing and event.Dragging() and event.LeftIsDown():
                dc = wx.BufferedDC(wx.ClientDC(self), self.buffer)
                dc.SetPen(self.pen)
                pos = event.GetPosition()
                coords = (pos.x, pos.y)
                self.curLine.append(coords)
                dc.DrawLine(*(self.pos.x, self.pos.y, pos.x, pos.y))
                self.pos = pos
        else:
            event.Skip()

    def OnMouseUp(self, event):
        """called when the left mouse button is released"""
        if self.isEditing:
            if self.HasCapture() and self.isDrawing:
                command = AddLineCommand(True, 'Add Line', self, self.cardIndex,
                                         ("pen", self.colour, self.thickness, self.curLine) )
                self.command_processor.Submit(command)
                self.curLine = []
                self.isDrawing = False
                self.ReleaseMouse()
        else:
            event.Skip()

    def OnKeyDown(self, event):
        self.uiCard.OnKeyDown(event)

    def OnKeyUp(self, event):
        self.uiCard.OnKeyUp(event)

    def OnSize(self, event):
        """
        Called when the window is resized.  We set a flag so the idle
        handler will resize the buffer.
        """
        self.reInitBuffer = True
        event.Skip()

    def OnIdle(self, event):
        """
        If the size was changed then resize the bitmap used for double
        buffering to match the window size.  We do it in Idle time so
        there is only one refresh after resizing is done, not lots while
        it is happening.
        """
        if self.reInitBuffer:
            self.InitBuffer()
            self.Refresh(False)

        if self.showCardPending:
            self.showCardPending = False
            if not self.isEditing and self.uiCard.model.runner:
                self.uiCard.model.runner.SetupForCurrentCard()
                self.uiCard.model.runner.RunHandler(self.uiCard.model, "OnShowCard", None)

        event.Skip()

    def OnPaint(self, event):
        """
        Called when the window is exposed.
        """
        # Create a buffered paint DC.  It will create the real
        # wx.PaintDC and then blit the bitmap to it when dc is
        # deleted.  Since we don't need to draw anything else
        # here that's all there is to it.
        dc = wx.BufferedPaintDC(self, self.buffer)

    def DrawShapes(self, dc):
        """
        Redraws all the shapes that have been drawn already.
        """
        for type, colour, thickness, line in self.uiCard.model.shapes:
            pen = wx.Pen(colour, thickness, wx.PENSTYLE_SOLID)
            dc.SetPen(pen)

            lastPos = None
            if type == "pen":
                for coords in line:
                    if lastPos:
                        dc.DrawLine(*(lastPos[0], lastPos[1], coords[0], coords[1]))
                    lastPos = coords

    # Event handlers for the popup menu, uses the event ID to determine
    # the colour or the thickness to set.
    def OnMenuSetColour(self, event):
        self.SetColour(self.menuColours[event.GetId()])

    def OnMenuSetThickness(self, event):
        self.SetThickness(event.GetId())

    def Undo(self):
        self.command_processor.Undo()
        if not self.command_processor.CanUndo():
            self.stackModel.SetDirty(False)
        self.InitBuffer()
        self.Refresh()

    def Redo(self):
        self.command_processor.Redo()
        self.InitBuffer()
        self.Refresh()

    # Observer pattern.  Listeners are registered and then notified
    # whenever doodle settings change.
    def AddListener(self, listener):
        self.listeners.append(listener)

    def Notify(self):
        for other in self.listeners:
            other.UpdateLine(self.colour, self.thickness)


class AddLineCommand(Command):
    parent = None

    def __init__(self, *args, **kwargs):
        super().__init__()
        self.stackView = args[2]
        self.cardIndex = args[3]
        self.line = args[4]

    def Do(self):
        self.stackView.LoadCardAtIndex(self.cardIndex)
        self.stackView.uiCard.model.shapes.append(self.line)
        return True

    def Undo(self):
        self.stackView.LoadCardAtIndex(self.cardIndex)
        if len(self.stackView.uiCard.model.shapes):
            self.stackView.uiCard.model.shapes.pop()
        return True


class AddUiViewCommand(Command):
    def __init__(self, *args, **kwargs):
        super().__init__(args, kwargs)
        self.stackView = args[2]
        self.cardIndex = args[3]
        self.viewType = args[4]
        self.viewModel = args[5] if len(args)>5 else None

    def Do(self):
        if self.viewType == "card":
            self.stackView.LoadCardAtIndex(None)
            self.stackView.stackModel.cardModels.insert(self.cardIndex, self.viewModel)
            self.stackView.LoadCardAtIndex(self.cardIndex)
        else:
            self.stackView.LoadCardAtIndex(self.cardIndex)
            uiView = self.stackView.AddUiViewInternal(self.viewType, self.viewModel)
            if not self.viewModel:
                self.viewModel = uiView.model
        return True

    def Undo(self):
        if self.viewType == "card":
            self.stackView.LoadCardAtIndex(None)
            self.stackView.stackModel.cardModels.remove(self.viewModel)
            index = self.cardIndex-1
            if index < 0: index = 0
            self.stackView.LoadCardAtIndex(index)
        else:
            self.stackView.LoadCardAtIndex(self.cardIndex)
            self.stackView.RemoveUiViewByModel(self.viewModel)
        return True


class RemoveUiViewCommand(Command):
    def __init__(self, *args, **kwargs):
        super().__init__(args, kwargs)
        self.stackView = args[2]
        self.cardIndex = args[3]
        self.viewModel = args[4]

    def Do(self):
        if self.viewModel.type == "card":
            self.stackView.LoadCardAtIndex(None)
            self.stackView.stackModel.cardModels.remove(self.viewModel)
            index = self.cardIndex
            if index >= len(self.stackView.stackModel.cardModels)-1: index = len(self.stackView.stackModel.cardModels)-1
            self.stackView.LoadCardAtIndex(index)
        else:
            self.stackView.LoadCardAtIndex(self.cardIndex)
            self.stackView.RemoveUiViewByModel(self.viewModel)
        return True

    def Undo(self):
        if self.viewModel.type == "card":
            self.stackView.LoadCardAtIndex(None)
            self.stackView.stackModel.cardModels.insert(self.cardIndex, self.viewModel)
            self.stackView.LoadCardAtIndex(self.cardIndex)
        else:
            self.stackView.LoadCardAtIndex(self.cardIndex)
            self.stackView.AddUiViewInternal(self.viewModel.type, self.viewModel)
        return True
