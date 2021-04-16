import wx
import wx.stc as stc
import keyword
import ast
import helpData

"""
The PythonEditor is used for the CodeEditor in the Designer's ControlPanel.
It offers syntax highlighting, brace pairing, and simple code autocompletion.
"""

TAB_WIDTH = 3

if wx.Platform == '__WXMSW__':
    faces = { 'mono' : 'Courier New',
              'helv' : 'Arial',
              'size' : 12,
              'size2': 10,
             }
elif wx.Platform == '__WXMAC__':
    faces = { 'mono' : 'Monaco',
              'helv' : 'Arial',
              'size' : 14,
              'size2': 12,
             }
else:
    faces = { 'mono' : 'Courier',
              'helv' : 'Helvetica',
              'size' : 14,
              'size2': 12,
             }


class PythonEditor(stc.StyledTextCtrl):
    def __init__(self, parent, undoHandler, **kwargs):
        super().__init__(parent=parent, **kwargs)

        self.undoHandler = undoHandler
        self.analyzer = CodeAnalyzer()

        self.SetAutoLayout(True)
        # self.SetConstraints(stc.LayoutAnchors(self, True, True, True, True))

        self.SetTabWidth(TAB_WIDTH)
        self.SetUseTabs(0)
        self.SetTabIndents(True)
        self.SetBackSpaceUnIndents(True)
        # self.SetIndentationGuides(True)
        self.SetUseAntiAliasing(True)
        self.SetMarginType(1, wx.stc.STC_MARGIN_NUMBER)
        self.SetMarginWidth(1, 24)
        self.SetUndoCollection(False)
        self.CmdKeyClear(ord("Z"), stc.STC_SCMOD_CTRL)
        self.CmdKeyClear(ord("Z"), stc.STC_SCMOD_CTRL|stc.STC_SCMOD_SHIFT)
        self.CmdKeyClear(ord("Y"), stc.STC_SCMOD_CTRL)

        self.StyleSetSpec(stc.STC_STYLE_DEFAULT,    'face:%(mono)s,fore:#000000,size:%(size)d' % faces)
        self.StyleSetSpec(stc.STC_STYLE_LINENUMBER, 'face:%(mono)s,fore:#999999,back:#EEEEEE' % faces)
        self.StyleSetSpec(stc.STC_STYLE_BRACELIGHT, 'face:%(mono)s,fore:#000000,back:#DDDDFF,bold' % faces)
        self.StyleSetSpec(stc.STC_STYLE_BRACEBAD,   'face:%(mono)s,fore:#000000,back:#FFCCCC,bold' % faces)
        self.StyleSetSpec(stc.STC_P_DEFAULT,        'face:%(mono)s,fore:#000000,size:%(size)d' % faces)
        self.StyleSetSpec(stc.STC_P_NUMBER,         'face:%(mono)s,fore:#007F7F' % faces)
        self.StyleSetSpec(stc.STC_P_CHARACTER,      'face:%(mono)s,fore:#007F7F,bold' % faces)
        self.StyleSetSpec(stc.STC_P_WORD,           'face:%(mono)s,fore:#1111EE' % faces)
        self.StyleSetSpec(stc.STC_P_CLASSNAME,      'face:%(mono)s,fore:#2222FF' % faces)
        self.StyleSetSpec(stc.STC_P_DEFNAME,        'face:%(mono)s,fore:#2222FF' % faces)
        self.StyleSetSpec(stc.STC_P_DECORATOR,      'face:%(mono)s,fore:#2222FF' % faces)
        self.StyleSetSpec(stc.STC_P_OPERATOR,       'face:%(mono)s,fore:#000044,bold' % faces)
        self.StyleSetSpec(stc.STC_P_IDENTIFIER,     'face:%(mono)s,fore:#000000' % faces)
        self.StyleSetSpec(stc.STC_P_STRING,         'face:%(mono)s,fore:#007F7F,bold' % faces)
        self.StyleSetSpec(stc.STC_P_STRINGEOL,      'face:%(mono)s,fore:#000000,back:#E0C0E0,eol' % faces)
        self.StyleSetSpec(stc.STC_P_COMMENTLINE,    'face:%(mono)s,fore:#888888' % faces)
        self.StyleSetSpec(stc.STC_P_COMMENTBLOCK,   'face:%(mono)s,fore:#999999' % faces)
        self.StyleSetSpec(stc.STC_P_TRIPLE,         'face:%(mono)s,fore:#999999' % faces)
        self.StyleSetSpec(stc.STC_P_TRIPLEDOUBLE,   'face:%(mono)s,fore:#999999' % faces)

        self.SetLexer(stc.STC_LEX_PYTHON)
        self.SetKeyWords(0, " ".join(keyword.kwlist))

        self.AutoCompSetAutoHide(False)
        self.AutoCompSetIgnoreCase(True)
        self.AutoCompSetFillUps("\t\r\n")
        self.AutoCompSetCancelAtStart(True)
        self.AutoCompSetDropRestOfWord(True)
        self.AutoCompSetCaseInsensitiveBehaviour(stc.STC_CASEINSENSITIVEBEHAVIOUR_IGNORECASE)
        self.Bind(stc.EVT_STC_AUTOCOMP_COMPLETED, self.OnACCompleted)
        self.Bind(stc.EVT_STC_AUTOCOMP_CANCELLED, self.OnACCancelled)
        self.Bind(stc.EVT_STC_AUTOCOMP_SELECTION_CHANGE, self.OnACSelectionChange)

        self.Bind(wx.EVT_SET_FOCUS, self.PyEditorOnFocus)
        self.Bind(wx.EVT_KILL_FOCUS, self.PyEditorOnLoseFocus)
        self.Bind(wx.EVT_KEY_DOWN, self.PyEditorOnKeyPress)
        self.Bind(stc.EVT_STC_ZOOM, self.PyEditorOnZoom)
        self.Bind(stc.EVT_STC_UPDATEUI, self.PyEditorOnUpdateUi)

    def PyEditorOnKeyPress(self, event):
        key = event.GetKeyCode()
        if key == stc.STC_KEY_RETURN:
            numSpaces = self.GetLineIndentation(self.GetCurrentLine())
            line = self.GetLine(self.GetCurrentLine())
            if line.strip()[-1:] == ":":
                numSpaces += TAB_WIDTH
            self.AddText("\n" + " "*numSpaces)
            self.analyzer.ScanCode(self.GetParent().stackManager.stackModel, self.GetParent().currentHandler)
            if self.AutoCompActive():
                self.AutoCompComplete()
        else:
            if key == ord("Z") and event.ControlDown():
                if not event.ShiftDown():
                    self.undoHandler.Undo()
                else:
                    self.undoHandler.Redo()
                return
            elif ord('a') <= key <= ord('z') or ord('A') <= key <= ord('Z'):
                wx.CallAfter(self.UpdateAC)
            elif self.AutoCompActive() and (key == wx.WXK_BACK or (event.ShiftDown() and key == ord('_')) or \
                                            (not event.ShiftDown() and ord('0') <= key <= ord('9'))):
                wx.CallAfter(self.UpdateAC)
            elif self.AutoCompActive() and (key in [stc.STC_KEY_ESCAPE, ord(' '), ord('['), ord('.')] or \
                    (event.ShiftDown() and ord('0') <= key <= ord('9'))):
                self.AutoCompCancel()
            event.Skip()

    def PyEditorOnZoom(self, event):
        # Disable Zoom
        z = event.GetEventObject().GetZoom()
        if z != 0:
            event.GetEventObject().SetZoom(0)

    def PyEditorOnUpdateUi(self, event):
        # check for matching braces
        braceAtCaret = -1
        braceOpposite = -1
        charBefore = None
        caretPos = self.GetCurrentPos()

        if caretPos > 0:
            charBefore = self.GetCharAt(caretPos - 1)
            styleBefore = self.GetStyleAt(caretPos - 1)

            # check before
            if charBefore and chr(charBefore) in "[]{}()" and styleBefore == stc.STC_P_OPERATOR:
                braceAtCaret = caretPos - 1

        # check after
        if braceAtCaret < 0:
            charAfter = self.GetCharAt(caretPos)
            styleAfter = self.GetStyleAt(caretPos)

            if charAfter and chr(charAfter) in "[]{}()" and styleAfter == stc.STC_P_OPERATOR:
                braceAtCaret = caretPos

        if braceAtCaret >= 0:
            braceOpposite = self.BraceMatch(braceAtCaret)

        if braceAtCaret != -1 and braceOpposite == -1:
            self.BraceBadLight(braceAtCaret)
        else:
            self.BraceHighlight(braceAtCaret, braceOpposite)
            pt = self.PointFromPosition(braceOpposite)
            self.Refresh(True, wx.Rect(pt.x, pt.y, 5,5))
            self.Refresh(False)

    def PyEditorOnFocus(self, event):
        self.UpdateACLists()
        event.Skip()

    def PyEditorOnLoseFocus(self, event):
        if self.AutoCompActive():
            self.AutoCompCancel()
        event.Skip()

    def UpdateACLists(self):
        self.analyzer.ScanCode(self.GetParent().stackManager.stackModel, self.GetParent().currentHandler)
        if self.AutoCompActive():
            self.AutoCompCancel()

    def UpdateAC(self):
        if self.IsInCommentOrString():
            # Don't autocomplete inside a comment or string
            if self.AutoCompActive():
                self.AutoCompCancel()
            return

        # Find the word start
        currentPos = self.GetCurrentPos()
        wordStartPos = self.WordStartPosition(currentPos, True)

        # Display the autocompletion list
        lenEntered = currentPos - wordStartPos
        if wordStartPos > 0 and chr(self.GetCharAt(wordStartPos-1)) == '.':
            acList = self.analyzer.ACAttributes
        else:
            acList = self.analyzer.ACNames

        if lenEntered > 0:
            prefix = self.GetTextRange(wordStartPos, currentPos).lower()
            acList = [s for s in acList if prefix in s.lower()]
            if len(acList):
                self.AutoCompShow(lenEntered, " ".join(acList))
            else:
                if self.AutoCompActive():
                    self.AutoCompCancel()

    def OnACCompleted(self, event):
        s = event.GetString()
        if s.endswith("()"):
            def moveBackOne():
                car = self.GetCurrentPos()
                self.SetSelection(car-1, car-1)
            wx.CallAfter(moveBackOne)
            self.AutoCompCancel()

    def OnACCancelled(self, event):
        self.GetParent().UpdateHelpText("")

    def OnACSelectionChange(self, event):
        s = event.GetString()
        if s:
            helpText = helpData.HelpData.GetHelpForName(s)
            if helpText:
                self.GetParent().UpdateHelpText(helpText)
                return
        self.GetParent().UpdateHelpText("")

    def IsInCommentOrString(self):
        # Use STC's syntax coloring styles to determine whether we're in a comment or string
        pos = self.GetCurrentPos()
        styles = [self.GetStyleAt(pos-i) for i in (0, 2)]
        inString = styles[0] == styles[1] and styles[1] in [stc.STC_P_CHARACTER, stc.STC_P_STRING,
                                                stc.STC_P_STRINGEOL, stc.STC_P_TRIPLE, stc.STC_P_TRIPLEDOUBLE]
        inComment = styles[1] in [stc.STC_P_COMMENTLINE, stc.STC_P_COMMENTBLOCK]
        return inString or inComment


class CodeAnalyzer(object):
    def __init__(self):
        super().__init__()
        self.varNames = []
        self.funcNames = []
        self.globalVars = helpData.HelpDataGlobals.variables.keys()
        self.globalFuncs = helpData.HelpDataGlobals.functions.keys()
        self.objNames = []
        self.objProps = []
        self.objMethods = []
        for cls in helpData.helpClasses:
            self.objProps += cls.properties.keys()
            self.objMethods += cls.methods.keys()
        self.ACNames = []
        self.ACAttributes = []

    def CollectCode(self, model):
        self.objNames.append(model.GetProperty("name"))
        code = "\n".join([s for s in model.handlers.values() if len(s)])
        for child in model.childModels:
            s = self.CollectCode(child)
            if len(s):
                code += "\n" + s
        return code

    def BuildACLists(self, handlerName):
        names = []
        names.extend(self.varNames)
        names.extend([s+"()" for s in self.funcNames])
        names.extend(self.globalVars)
        names.extend([s+"()" for s in self.globalFuncs])
        names.extend(self.objNames)
        names.extend(["False", "True", "None"])
        if "Mouse" in handlerName: names.append("mousePos")
        if "Key" in handlerName: names.append("keyName")
        if "Idle" in handlerName: names.append("elapsedTime")
        if "Message" in handlerName: names.append("message")
        names = list(set(names))
        names.sort(key=str.casefold)
        self.ACNames = names

        attributes = []
        attributes.extend(self.objProps)
        attributes.extend([s+"()" for s in self.objMethods])
        attributes.extend(self.objNames)
        attributes = list(set(attributes))
        attributes.sort(key=str.casefold)
        self.ACAttributes = attributes

    def ScanCode(self, model, handlerName):
        self.objNames = []
        code = self.CollectCode(model)
        try:
            root = ast.parse(code)

            self.varNames = set()
            self.funcNames = set()

            for node in ast.walk(root):
                if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                    self.varNames.add(node.id)
                elif isinstance(node, ast.FunctionDef):
                    self.funcNames.add(node.name)

            self.BuildACLists(handlerName)
        except SyntaxError:
            pass
