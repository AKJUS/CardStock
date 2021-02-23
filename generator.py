import wx
import uiButton
import uiTextField
import uiTextLabel
import uiImage
import uiShape
import uiGroup
import uiCard


class StackGenerator(object):
    @classmethod
    def UiViewFromModel(self, parent, stackManager, model):
        if model.type == "button":
            return uiButton.UiButton(parent, stackManager, model)
        elif model.type == "textfield" or type == "field":
            return uiTextField.UiTextField(parent, stackManager, model)
        elif model.type == "textlabel" or type == "label":
            return uiTextLabel.UiTextLabel(parent, stackManager, model)
        elif model.type == "image":
            return uiImage.UiImage(parent, stackManager, model)
        elif model.type == "group":
            return uiGroup.UiGroup(parent, stackManager, model)
        elif model.type in ["pen", "line", "oval", "rect", "roundrect"]:
            return uiShape.UiShape(parent, stackManager, type, model)
        return None

    @classmethod
    def ModelFromData(cls, stackManager, data):
        m = None
        if data["type"] == "card":
            m = uiCard.CardModel(stackManager)
        elif data["type"] == "button":
            m = uiButton.ButtonModel(stackManager)
        elif data["type"] == "textfield":
            m = uiTextField.TextFieldModel(stackManager)
        elif data["type"] == "textlabel":
            m = uiTextLabel.TextLabelModel(stackManager)
        elif data["type"] == "image":
            m = uiImage.ImageModel(stackManager)
        elif data["type"] == "group":
            m = uiGroup.GroupModel(stackManager)
        elif data["type"] in ["pen", "line", "oval", "rect", "roundrect"]:
            m = uiShape.UiShape.CreateModelForType(stackManager, data["type"])
        m.SetData(data)
        return m
