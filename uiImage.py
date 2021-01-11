#!/usr/bin/python

# This is a draggable View, for adding a UI elements from the palate to the Page.

import os
import wx
from uiView import UiView, ViewModel

class UiImage(UiView):
    def __init__(self, stackView, model=None):
        if not model:
            model = ImageModel()
            model.SetProperty("name", stackView.uiPage.model.GetNextAvailableNameForBase("image_"))

        img = self.GetImg(model)
        container = wx.Window(stackView)
        container.Enable(True)
        self.imgView = wx.StaticBitmap(container, bitmap=img)
        self.imgView.Enable(True)
        self.imgView.SetScaleMode(self.AspectStrToInt(model.GetProperty("fit")))
        self.imgView.SetCursor(wx.Cursor(wx.CURSOR_HAND))

        super().__init__(stackView, model, container)
        self.BindEvents(self.imgView)

    def AspectStrToInt(self, str):
        if str == "Center":
            return 0
        elif str == "Stretch":
            return 1
        elif str == "Scale":
            return 3
        else:
            return 3 # Default to Scale

    def GetImg(self, model):
        file = model.GetProperty("file")
        if os.path.exists(file):
            img = wx.Image(file, wx.BITMAP_TYPE_ANY).ConvertToBitmap()
        else:
            img = wx.Image(100,100, True).ConvertToBitmap()
        return img

    def OnResize(self, event):
        super().OnResize(event)
        self.imgView.SetSize(self.view.GetSize())
        event.Skip()

    def OnPropertyChanged(self, model, key):
        super().OnPropertyChanged(model, key)
        if key == "file":
            img = self.GetImg(self.model)
            self.imgView.SetBitmap(img)
            self.imgView.SetSize(self.view.GetSize())
        elif key == "fit":
            self.imgView.SetScaleMode(self.AspectStrToInt(model.GetProperty("fit")))


class ImageModel(ViewModel):
    def __init__(self):
        super().__init__()
        self.type = "image"

        self.properties["file"] = ""
        self.properties["fit"] = "Scale"

        self.propertyTypes["file"] = "string"
        self.propertyTypes["fit"] = "choice"
        self.propertyChoices["fit"] = ["Center", "Stretch", "Fill"]

        # Custom property order and mask for the inspector
        self.propertyKeys = ["name", "file", "fit", "position", "size"]

    def GetFile(self): return self.GetProperty("file")
    def SetFile(self, text): self.SetProperty("file", text)
