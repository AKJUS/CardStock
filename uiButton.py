#!/usr/bin/python

# This is a draggable View, for adding a UI elements from the palate to the Card.

import wx
from uiView import UiView, ViewModel


class UiButton(UiView):
    def __init__(self, parent, stackView, model=None):
        button = wx.Button(parent=parent.view, id=wx.ID_ANY, label="Button")  # style=wx.BORDER_NONE

        if not model:
            model = ButtonModel(stackView)
            model.SetProperty("name", stackView.uiCard.model.GetNextAvailableNameInCard("button_"), False)

        button.SetCursor(wx.Cursor())
        super().__init__(parent, stackView, model, button)

    def SetView(self, view):
        super().SetView(view)
        view.SetLabel(self.model.GetProperty("title"))
        view.Bind(wx.EVT_BUTTON, self.OnButton)

    def OnPropertyChanged(self, model, key):
        super().OnPropertyChanged(model, key)
        if key == "title":
            self.view.SetLabel(str(self.model.GetProperty(key)))

    def OnButton(self, event):
        if not self.stackView.isEditing:
            if self.stackView.runner and "OnClick" in self.model.handlers:
                self.stackView.runner.RunHandler(self.model, "OnClick", event)


class ButtonModel(ViewModel):
    def __init__(self, stackView):
        super().__init__(stackView)
        self.type = "button"

        # Add custom handlers to the top of the list
        handlers = {"OnClick": ""}
        for k,v in self.handlers.items():
            handlers[k] = v
        self.handlers = handlers

        self.properties["title"] = "Button"
        self.propertyTypes["title"] = "string"

        # Custom property order and mask for the inspector
        self.propertyKeys = ["name", "title", "position", "size"]

    def GetTitle(self): return self.GetProperty("title")
    def SetTitle(self, text): self.SetProperty("title", text)
    def GetText(self): return self.GetProperty("title")
    def SetText(self, text): self.SetProperty("title", text)

    def DoClick(self):
        if self.stackView.runner:
            self.stackView.runner.RunHandler(self, "OnClick", None)
