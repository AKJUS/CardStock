from browser import self as worker
import wx_compat as wx
from models import *
from views import *
import runner
import json


class StackManager(object):
    def __init__(self):
        super().__init__(self)
        self.stackModel = None
        self.uiCard = UiCard(None, self, None)
        self.cardIndex = None
        self.didSetup = False
        self.runner = None
        self.lastPeriodic = time()
        self.lastFrame = self.lastPeriodic

    def SetDown(self):
        self.uiCard.SetDown()
        self.uiCard = None
        self.stackModel.SetDown()
        self.stackModel.DismantleChildTree()
        self.stackModel = None

    def Unload(self):
        self.uiCard.UnLoad()
        for ui in self.uiCard.uiViews.values():
            ui.SetDown()
        self.uiCard.uiViews = {}

        self.stackModel.SetDown()
        self.stackModel.DismantleChildTree()

    def LoadFromStr(self, stackStr):
        stackJSON = json.loads(stackStr)
        self.Load(stackJSON)

    def Load(self, stackJSON):
        if self.stackModel:
            self.Unload()

        if self.runner:
            self.runner.SetDown()
        self.runner = runner.Runner(self)
        self.stackModel = StackModel(self)
        self.stackModel.SetData(stackJSON)
        s = self.stackModel.GetProperty("size")
        worker.stackWorker.SendAsync(("canvasSetSize", s.width, s.height))
        self.lastPeriodic = time()
        self.runner.StartStack()
        self.cardIndex = None
        self.didSetup = False
        self.LoadCardAtIndex(0)

    def RunSetupIfNeeded(self):
        if not self.didSetup:
            self.stackModel.RunSetup(self.runner)
            self.didSetup = True

    def LoadCardAtIndex(self, cardIndex, reload=False):
        if len(self.stackModel.childModels) > cardIndex:
            if reload or cardIndex != self.cardIndex:
                worker.stackWorker.SendAsync(("willUnload",))
                worker.stackWorker.Wait(0.02) # wait for pending frame render before changing cards
                self.cardIndex = cardIndex
                card = self.stackModel.childModels[cardIndex]
                self.runner.SetupForCard(card)
                self.uiCard.Load(card)
                worker.stackWorker.SendAsync(("didLoad",))

    def OnFrame(self):
        if not self.didSetup:
            return

        now = time()
        elapsedTime = now - self.lastFrame
        self.lastFrame = now

        didRun = False
        allUi = self.uiCard.GetAllUiViews()
        onFinishedCalls = []
        if self.uiCard.RunAnimations(onFinishedCalls, elapsedTime):
            didRun = True
        for ui in allUi:
            if ui.RunAnimations(onFinishedCalls, elapsedTime):
                didRun = True
        # Let all animations process, before running their onFinished handlers,
        # which could start new animations.
        for c in onFinishedCalls:
            c()
        if len(onFinishedCalls):
            didRun = True

        # Check for all collisions
        collisions = {}
        for ui in allUi:
            ui.FindCollisions(collisions)

        # Perform any bounces
        for (k,v) in collisions.items():
            v[0].PerformBounce(v, elapsedTime)
            didRun = True

        if didRun:
            worker.stackWorker.SendAsync(("render",))

        elapsedTime = now - self.lastPeriodic
        if elapsedTime >= 0.03:
            self.lastPeriodic = now
            self.uiCard.OnKeyHold()
            self.uiCard.OnPeriodic()

    def ConvPoint(self, p):
        cardSize = self.uiCard.model.GetProperty("size")
        return wx.Point(p.x, cardSize.height - p.y)

    def ConvRect(self, r):
        cardSize = self.uiCard.model.GetProperty("size")
        return wx.Rect(r.Left, cardSize.height - (r.Top+r.Height), r.Width, r.Height)

    def GetUiViewByModel(self, model):
        def FindSubView(uiView):
            if uiView.model == model:
                return uiView
            for ui in uiView.uiViews.values():
                found = FindSubView(ui)
                if found:
                    return found
            return None
        return FindSubView(self.uiCard)

    def AddUiViewInternal(self, model):
        uiView = None
        objType = model.type

        if objType == "button":
            uiView = UiButton(self.uiCard, self, model)
        elif objType == "textfield" or objType == "field":
            uiView = UiTextField(self.uiCard, self, model)
        elif objType == "textlabel" or objType == "label":
            uiView = UiTextLabel(self.uiCard, self, model)
        elif objType == "image":
            uiView = UiImage(self.uiCard, self, model)
        elif objType == "webview":
            uiView = UiWebView(self.uiCard, self, model)
        elif objType == "group":
            uiView = UiGroup(self.uiCard, self, model)
            uiView.LoadChildren()
        elif objType in ["pen", "line", "oval", "rect", "polygon", "roundrect"]:
            uiView = UiShape(self.uiCard, self, model)

        if not model.GetCard():
            uiView.model.SetProperty("name", self.uiCard.model.DeduplicateNameInCard(
                uiView.model.GetProperty("name"), exclude=[]), notify=False)

        if uiView:
            self.uiCard.uiViews[model] = uiView
            if uiView.model not in self.uiCard.model.childModels:
                self.uiCard.model.AddChild(uiView.model)

        return uiView

    def RemoveFabObjs(self, uiView):
        ids = []
        def remUi(ui):
            print("removing", ui.fabIds)
            ids.extend(ui.fabIds)
            for u in ui.uiViews.values():
                remUi(u)
        remUi(uiView)
        print("remAll", ids)
        worker.stackWorker.SendAsync(("fabDel", *ids))

    def AddUiViewsFromModels(self, models):
        """
        Adds views for the given models, and adds the models as children of the current card model
        if they're not already somewhere in the stack's model tree.  To split model changes from view changes,
        just add the model to the stack before calling this, and then this method will only make changes to the views.
        """
        models = [m for m in models if not m.didSetDown]
        self.uiCard.model.DeduplicateNamesForModels(models)
        for m in models:
            self.AddUiViewInternal(m)

    def RemoveUiViewByModel(self, viewModel):
        """
        Removes views for the given models, and removes the models from the stack if they're still in the stack tree.
        To split model changes from view changes, just remove the model from the stack before calling this, and then
        this method will only make changes to the views.
        """
        ui = self.GetUiViewByModel(viewModel)
        if ui:
            del self.uiCard.uiViews[viewModel]
            if ui.model.parent:
                self.uiCard.model.RemoveChild(ui.model)
            self.RemoveFabObjs(ui)
            worker.stackWorker.SendAsync(("render",))
        else:
            if viewModel.parent:
                viewModel.parent.RemoveChild(viewModel)

    def AddCard(self):
        newCard = CardModel(self)
        newCard.SetProperty("name", newCard.DeduplicateName("card_1",
                                                            [m.GetProperty("name") for m in self.stackModel.childModels]))
        self.stackModel.InsertCardModel(self.cardIndex+1, newCard)
        newCard.RunSetup(self.runner)
        self.LoadCardAtIndex(self.cardIndex+1)

    def DuplicateCard(self, card=None):
        newCard = CardModel(self)
        if not card:
            card = self.stackModel.childModels[self.cardIndex]
        newCard.SetData(card.GetData())
        newCard.SetProperty("name", newCard.DeduplicateName(newCard.GetProperty("name"),
                                                            [m.GetProperty("name") for m in self.stackModel.childModels]))
        self.stackModel.InsertCardModel(self.cardIndex+1, newCard)
        newCard.RunSetup(self.runner)
        self.LoadCardAtIndex(self.cardIndex+1)
        return newCard

    def RemoveCard(self):
        self.RemoveCardRaw(self.stackModel.childModels[self.cardIndex])

    def RemoveCardRaw(self, cardModel):
        if len(self.stackModel.childModels) > 1:
            index = self.stackModel.childModels.index(cardModel)
            self.stackModel.RemoveCardModel(cardModel)
            if index == self.cardIndex:
                if index == len(self.stackModel.childModels):
                    index = len(self.stackModel.childModels) - 1
                if index >= 0:
                    self.LoadCardAtIndex(index)

    def GroupModelsInternal(self, models, group=None, name=None):
        """ Groups both the models and uiView objects, so while running, call this within a @RunOnMainSync. """
        if len(models) > 1:
            card = models[0].GetCard()
            if not group:
                group = GroupModel(self)
                if not name:
                    name = "group"
                group.SetProperty("name", card.GetNextAvailableNameInCard(name), notify=False)
            else:
                group.SetBackUp(self)
            validModels = []
            for m in models:
                if m.GetCard() == card:
                    validModels.append(m)
                    self.RemoveUiViewByModel(m)
                    m.SetBackUp(self)
            group.AddChildModels(validModels)
            if card == self.uiCard.model:
                self.AddUiViewsFromModels([group])
            else:
                card.AddChild(group)
        return group

    def UngroupModelsInternal(self, groups):
        """ Ungroups both the models and uiView objects, so while running, call this within a @RunOnMainSync. """
        modelSets = []
        if len(groups) > 0:
            for group in groups:
                childModels = []
                modelSets.append(childModels)
                for child in group.childModels.copy():
                    childModels.append(child)
                    group.RemoveChild(child)
                    child.SetBackUp(self)
                if group.GetCard() == self.uiCard.model:
                    self.RemoveUiViewByModel(group)
                    self.AddUiViewsFromModels(childModels)
                else:
                    p = group.parent
                    p.RemoveChild(group)
                    for child in childModels:
                        p.AddChild(child)

        return modelSets

    def OnPropertyChanged(self, model, key):
        ui = self.GetUiViewByModel(model)
        if ui:
            ui.OnPropertyChanged(key)

    @classmethod
    def ModelFromData(cls, stackManager, data):
        m = None
        if data["type"] == "card":
            m = CardModel(stackManager)
        elif data["type"] == "button":
            m = ButtonModel(stackManager)
        elif data["type"] == "textfield":
            m = TextFieldModel(stackManager)
        elif data["type"] == "textlabel":
            m = TextLabelModel(stackManager)
        elif data["type"] == "image":
            m = ImageModel(stackManager)
        elif data["type"] == "webview":
            m = WebViewModel(stackManager)
        elif data["type"] == "group":
            m = GroupModel(stackManager)
        elif data["type"] in ["pen", "line"]:
            m = LineModel(stackManager, data["type"])
        elif data["type"] in ["rect", "oval", "polygon"]:
            m = ShapeModel(stackManager, data["type"])
        elif data["type"] == "roundrect":
            m = RoundRectModel(stackManager, data["type"])

        m.SetData(data)
        return m

    @classmethod
    def ModelFromType(cls, stackManager, typeStr):
        m = None
        if typeStr == "card":
            m = CardModel(stackManager)
        elif typeStr == "button":
            m = ButtonModel(stackManager)
        elif typeStr == "textfield" or typeStr == "field":
            m = TextFieldModel(stackManager)
        elif typeStr == "textlabel" or typeStr == "label":
            m = TextLabelModel(stackManager)
        elif typeStr == "image":
            m = ImageModel(stackManager)
        elif typeStr == "webview":
            m = WebViewModel(stackManager)
        elif typeStr == "group":
            m = GroupModel(stackManager)
        elif typeStr in ["pen", "line"]:
            m = LineModel(stackManager, typeStr)
        elif typeStr in ["rect", "oval", "polygon"]:
            m = ShapeModel(stackManager, typeStr)
        elif typeStr == "roundrect":
            m = RoundRectModel(stackManager, typeStr)

        return m

    @classmethod
    def UiViewFromModel(cls, parent, stackManager, model):
        if model.type == "button":
            return UiButton(parent, stackManager, model)
        elif model.type == "textfield" or model.type == "field":
            return UiTextField(parent, stackManager, model)
        elif model.type == "textlabel" or model.type == "label":
            return UiTextLabel(parent, stackManager, model)
        elif model.type == "image":
            return UiImage(parent, stackManager, model)
        elif model.type == "webview":
            return UiWebView(parent, stackManager, model)
        elif model.type == "group":
            return UiGroup(parent, stackManager, model)
        elif model.type in ["line", "pen", "oval", "rect", "roundrect", "polygon"]:
            return UiShape(parent, stackManager, model)
        return None
