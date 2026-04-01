# Purpose:
# This module parses the custom question template format and generates rendered output

# Function:
# - Splits full template text into variables/question/answer/incorrect sections
# - Evaluates variable calls dynamically against question_library
# - Renders question and answer text using Jinja blocks
# - Generates incorrect answers from line-by-line function calls
# - Returns user-facing parse/render errors as: ERROR at: <line content>

from __future__ import annotations

from dataclasses import dataclass      #Dataclass keeps section payloads explicit and readable
from functools import wraps            #Wraps preserves function metadata for signature checks
import inspect                         #Inspect discovers callable library functions dynamically
import re                              #Regex performs DSL and template pattern matching
import random                          #Random selects one option per incorrect-line generator call
from typing import Any                 #Any allows simple extension for future variable types
from jinja2 import Environment, StrictUndefined, TemplateSyntaxError    #Jinja renders template text and reports syntax issues
import question_library                                                 #Question library module is imported directly for dynamic function lookup
from question_library import UIntValue                                  #UIntValue type is used for serialization checks


# TemplateProcessingError provides one consistent error type for the app layer
class TemplateProcessingError(Exception):
    pass

# TemplateSections stores each required template block as raw text
@dataclass
class TemplateSections:
    variables: str
    question: str
    answer: str
    incorrect: str


# sectionHeaders defines the only valid root block names.
sectionHeaders = {"variables", "question", "answer", "incorrect"}


# ____________________________________ LIBRARY INTERACTION FUNCTIONS SECTION ____________________________________

# ================ getLibraryFunctionRegistry: DISCOVERS CALLABLE FUNCTIONS FROM LIBRARY =============
# returns a dictionary of function names and their associated functions. e.g. registry["loopPrint"]("{{ var1 }} {{ var2 }}", var1, var2)
def bindRngToFunction(function: Any, rng: random.Random) -> Any:
    signature = inspect.signature(function)
    acceptsRng = "rng" in signature.parameters
    acceptsKwargs = any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD for parameter in signature.parameters.values()
    )

    if not acceptsRng and not acceptsKwargs:
        return function

    @wraps(function)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        if "rng" not in kwargs:
            kwargs["rng"] = rng
        return function(*args, **kwargs)

    wrapped.__signature__ = signature
    return wrapped


def getLibraryFunctionRegistry(rng: random.Random | None = None) -> dict[str, Any]:
    registry: dict[str, Any] = {}
    for name, member in inspect.getmembers(question_library, inspect.isfunction):
        if name.startswith("_"):                # don't add functions that start with _ to the registry, in case we want any private functions
            continue
        if rng is None:
            registry[name] = member
        else:
            registry[name] = bindRngToFunction(member, rng)
    return registry


# ================ simpleSplitArgs: SPLITS ARGUMENTS BY COMMA (NESTED + QUOTED SAFE) ================
# returns a list of argument tokens, respecting nested parentheses and quoted strings.
# e.g. simpleSplitArgs('UInt(nameGen(), 1, 50), "a,b", x') -> ['UInt(nameGen(), 1, 50)', '"a,b"', 'x']
def simpleSplitArgs(argumentText: str) -> list[str]:
    cleaned = argumentText.strip()
    if not cleaned:
        return []

    parts: list[str] = []
    current: list[str] = []
    depth = 0
    quote: str | None = None
    escape = False

    for ch in cleaned:
        if escape:                              # Treat escaped character as literal when inside quotes
            current.append(ch)
            escape = False
            continue

        if ch == "\\" and quote is not None:    # Allow escaped quotes or backslashes within a quoted string
            current.append(ch)
            escape = True
            continue

        if quote is not None:                   # Inside quotes, everything is literal until the matching quote closes
            current.append(ch)
            if ch == quote:
                quote = None
            continue

        if ch in {"'", '"'}:                    # Start of a quoted string segment
            current.append(ch)
            quote = ch
            continue

        if ch == "(":                           # Track nesting depth to avoid splitting on commas inside parentheses
            depth += 1
            current.append(ch)
            continue

        if ch == ")":                           # Decrease nesting depth when leaving a parenthesized segment
            if depth > 0:
                depth -= 1
            current.append(ch)
            continue

        if ch == "," and depth == 0:            # Top-level comma ends the current argument token
            token = "".join(current).strip()
            if token:
                parts.append(token)
            current = []
            continue

        # Regular character outside quotes/commas/parens
        current.append(ch)

    # Flush the trailing token after the loop
    token = "".join(current).strip()
    if token:
        parts.append(token)

    return parts


# ================ parseArgumentValue: CONVERTS SIMPLE TOKENS TO PYTHON VALUES ================
# returns the best-effort Python value for a token (strings, numbers, booleans, None, context vars)
# e.g. parseArgumentValue('"hi"', ctx) -> "hi", parseArgumentValue("count", ctx) -> ctx["count"]
def parseArgumentValue(valueText: str, context: dict[str, Any]) -> Any:
    text = valueText.strip()

    if not text:                                                                                        # Empty token maps to empty string for graceful downstream formatting
        return ""

    if (text.startswith('"') and text.endswith('"')) or (text.startswith("'") and text.endswith("'")):  # Quoted literal string: strip the surrounding quotes
        return text[1:-1]

    if re.fullmatch(r"-?\d+", text):                                                                    # Integer literal
        return int(text)

    if re.fullmatch(r"-?\d+\.\d+", text):                                                               # Float literal
        return float(text)

    if text in {"True", "False"}:                                                                       # Boolean literal
        return text == "True"

    if text == "None":                                                                                  # None literal
        return None

    if text in context:                                                                                 # Variable reference from the current evaluation context
        return context[text]

    # Support simple dotted attribute access like var.attr or var.attr.subattr
    dottedMatch = re.match(r"^([A-Za-z_]\w*)(\.[A-Za-z_]\w*)+$", text)
    if dottedMatch:
        return resolveDottedValue(text, context)

    # Fallback: treat as a bare string token (e.g., identifiers or unknown literals)
    return text

# ================ resolveDottedValue: RESOLVES DOTTED ATTRIBUTE PATHS FROM CONTEXT ================
def resolveDottedValue(pathText: str, context: dict[str, Any]) -> Any:
    parts = pathText.split(".")
    rootName = parts[0]
    if rootName not in context:
        raise ValueError(f"{pathText} is undefined.")

    current = context[rootName]
    for attr in parts[1:]:
        if not hasattr(current, attr):
            raise ValueError(f"{pathText} is not a valid attribute path.")
        current = getattr(current, attr)

    return current


# ================ parseFunctionArguments: PARSES POSITIONAL + MINIMAL NAMED ARGUMENTS ================
def parseFunctionArguments(argumentText: str, context: dict[str, Any]) -> tuple[list[Any], dict[str, Any]]:
    # Initialize containers for positional arguments and keyword arguments.
    positionalArgs: list[Any] = []
    keywordArgs: dict[str, Any] = {}

    # Split the raw argument text into comma-separated tokens (respecting nesting/quotes), then classify each token as either a named arg (key: value) or positional value
    for part in simpleSplitArgs(argumentText):                                                      # Named arguments use "key: value" syntax; positional args are everything else
        namedMatch = re.match(r"^([A-Za-z_]\w*)\s*:\s*(.+)$", part)
        if namedMatch:                                                                              # Convert the value token to a Python value and store it under the given key
            keywordArgs[namedMatch.group(1)] = parseArgumentValue(namedMatch.group(2), context)
        else:                                                                                       # Convert the positional token to a Python value and append in order
            positionalArgs.append(parseArgumentValue(part, context))

    # Return both lists so the caller can invoke the target function correctly
    return positionalArgs, keywordArgs


# ================ callLibraryFunctionByName: EXECUTES ONE LIBRARY FUNCTION BY NAME ================
# e.g. callLibraryFunctionByName("UInt", 'nameGen(), 1, 50', ctx, registry, targetVarName="x")
def callLibraryFunctionByName(
    functionName: str,
    argumentText: str,
    context: dict[str, Any],
    functionRegistry: dict[str, Any],
    targetVarName: str | None = None,
) -> Any:
    if functionName not in functionRegistry:                                        # Fail fast with a template error if the function is not registered
        raise errorAt(f"{functionName}({argumentText})")

    positionalArgs, keywordArgs = parseFunctionArguments(argumentText, context)     # Parse raw argument text into positional and keyword args with value conversion
    function = functionRegistry[functionName]                                       # Look up the actual callable from the registry

    if targetVarName and "name" not in keywordArgs:                                 # Inject name=<var> if the target function accepts it and it wasn't provided explicitly
        signature = inspect.signature(function)
        acceptsName = "name" in signature.parameters
        acceptsKwargs = any(
            parameter.kind == inspect.Parameter.VAR_KEYWORD for parameter in signature.parameters.values()
        )
        nameAlreadyPassedPositionally = False
        if acceptsName:                                                             # Determine if "name" was already provided positionally to avoid overriding it
            parameterOrder = list(signature.parameters.keys())
            nameIndex = parameterOrder.index("name")
            if len(positionalArgs) > nameIndex:
                nameAlreadyPassedPositionally = True
        if (acceptsName and not nameAlreadyPassedPositionally) or acceptsKwargs:    # Safe to inject name if accepted (directly or via **kwargs)
            keywordArgs["name"] = targetVarName

    try:
        # Execute the library function with parsed args
        result = function(*positionalArgs, **keywordArgs)
        if targetVarName and hasattr(result, "__dict__"):
            try:
                # Stamp a varId for later reference (best-effort, non-fatal)
                setattr(result, "varId", targetVarName)
            except Exception:
                pass
        return result
    except Exception:
        # Normalize any execution error into a template error at the call site
        raise errorAt(f"{functionName}({argumentText})")


# ____________________________________________ PARSING HELPER FUNCTIONS SECTION _________________________________________

# ================ errorAt: GENERALIZES ERROR REPORTING (NOT REALLY SMART) ================
# e.g. errorAt("someFunction(x, y)") -> TemplateProcessingError("ERROR at: someFunction(x, y)")
def errorAt(lineContent: str) -> TemplateProcessingError:
    return TemplateProcessingError(f"ERROR at: {lineContent.rstrip()}")


# ================ normalizeLineExpression: FIXES NESTED QUOTES INSIDE line("...") ================
# returns a safe Python expression for line(...) when the format string contains unescaped quotes.
# e.g. line("std::cout << "Hello {{ var1 }}""") -> line('''std::cout << "Hello {{ var1 }}'''")
def normalizeLineExpression(expression: str) -> str:
    stripped = expression.strip()
    if not stripped.startswith("line(") or not stripped.endswith(")"):
        return expression

    inner = stripped[len("line(") : -1].strip()
    if len(inner) < 2:
        return expression

    quote = inner[0]
    if quote not in {"'", '"'} or inner[-1] != quote:
        return expression

    content = inner[1:-1]
    escaped = False
    has_unescaped_quote = False
    for ch in content:
        if escaped:
            escaped = False
            continue
        if ch == "\\":
            escaped = True
            continue
        if ch == quote:
            has_unescaped_quote = True
            break

    if not has_unescaped_quote:
        return expression

    # Swap to triple quotes to allow nested quotes inside the format string.
    if quote == '"':
        safe = content.replace("'''", "\\'\\'\\'")
        return f"line('''{safe}''')"

    safe = content.replace('"""', '\\"""')
    return f'line("""{safe}""")'


# ================ indentAfterNewline: INDENTS MULTI-LINE INSERTS TO MATCH THEIR LINE ================
# returns a string where every newline is followed by the given indent
# e.g. indentAfterNewline("a\nb", "    ") -> "a\n    b"
def indentAfterNewline(value: Any, indent: str) -> str:
    text = str(value)
    if not text or not indent:
        return text
    return text.replace("\n", "\n" + indent)

# ================ applyInlineIndentFilter: WRAPS INLINE JINJA BLOCKS WITH INDENT FILTER ================
# Injects an indent filter into {{ ... }} expressions that start a line with whitespace.
# This makes multi-line inserts keep the same tab/space prefix as the placeholder line.
def applyInlineIndentFilter(templateText: str) -> str:
    def replacer(match: re.Match[str]) -> str:
        indent = match.group(1)
        expression = match.group(2).strip()
        if "indent_after_newline" in expression:
            return match.group(0)

        safeIndent = indent.replace("\\", "\\\\").replace("'", "\\'")
        return f"{indent}{{{{ ({expression}) | indent_after_newline('{safeIndent}') }}}}"

    return re.sub(r"(?m)^([ \t]*){{\s*(.+?)\s*}}", replacer, templateText)


# ____________________________________________ TEMPLATE PARSING SECTION _________________________________________

# ================ parseSections: SEPARATES PLAIN TEXT TEMPLATE INTO NAMED SECTION STRINGS ================
def parseSections(templateText: str) -> TemplateSections:
    currentSection: str | None = None                                               # Track which section we're currently collecting lines for
    sectionLines: dict[str, list[str]] = {name: [] for name in sectionHeaders}      # Initialize storage for each required template section

    for rawLine in templateText.splitlines():
        strippedLine = rawLine.strip()                                                              # Normalize whitespace for header detection while preserving raw content for storage/errors
        sectionMatch = re.match(r"^(variables|question|answer|incorrect)\s*:\s*$", strippedLine)    # Detect section headers like "variables:" or "question:" on their own line

        if sectionMatch:                                                            # Switch the active section when a header is found
            currentSection = sectionMatch.group(1)
            continue

        if currentSection is None:                                                  # Any non-empty text before the first header is invalid
            if strippedLine:
                raise errorAt(rawLine)
            continue

        # Append the raw line to the current section's content
        sectionLines[currentSection].append(rawLine)

    # Missing sections are treated as empty (no error) to support prompt-only questions.

    # Join the collected lines for each section into the final TemplateSections payload
    return TemplateSections(
        variables="\n".join(sectionLines["variables"]),
        question="\n".join(sectionLines["question"]),
        answer="\n".join(sectionLines["answer"]),
        incorrect="\n".join(sectionLines["incorrect"]),
    )


# ================ evaluateVariables: EVALUATES VARIABLE ASSIGNMENT EXPRESSIONS ================
# Returns a context dict mapping variable names to evaluated values, supports nested library calls and references to previously defined variables
# e.g. evaluateVariables('x = UInt(nameGen(), 1, 50)')
def evaluateVariables(variablesBlock: str, rng: random.Random | None = None) -> dict[str, Any]:
    context: dict[str, Any] = {}
    functionRegistry = getLibraryFunctionRegistry(rng)                              # Build the function registry once for lookups and eval scope

    for rawLine in variablesBlock.splitlines():                                     # Normalize line content and skip blanks for forgiving template formatting
        line = rawLine.strip()
        if not line:
            continue

        # Validate and extract "name = expression" assignments
        assignmentMatch = re.match(r"^([A-Za-z_]\w*)\s*=\s*(.+?)\s*;?\s*$", line)
        if not assignmentMatch:
            raise errorAt(rawLine)

        varName = assignmentMatch.group(1)
        expression = normalizeLineExpression(assignmentMatch.group(2))

        try:
            # Build a safe evaluation scope for library functions and prior variables
            evalScope: dict[str, Any] = {}
            evalScope.update(functionRegistry)
            evalScope.update(context)
            evalScope.update({"True": True, "False": False, "None": None})
            value = eval(expression, {"__builtins__": {}}, evalScope)               # Evaluate the expression as Python code (nested calls allowed)
        except Exception:                                                           # Surface evaluation errors at the original line for user-friendly reporting
            raise errorAt(rawLine)

        # Stamp the template variable name for loopPrint name-based access (best-effort).
        if hasattr(value, "__dict__"):
            try:
                setattr(value, "varId", varName)
            except Exception:
                pass

        context[varName] = value                                                    # Save the evaluated value in the context for later lines and other sections

    return context                                                                  # Return the fully populated variable context


# ================ renderJinja: RENDERS A TEMPLATE BLOCK WITH STRICT UNDEFINEDS ================
# e.g. renderJinja("Hello {{ name }}", {"name": "Ada"}) -> "Hello Ada"
# Returns rendered template text, executing a full-line library call if present; used by question/answer/incorrect parsing for consistent Jinja rendering
# Create a Jinja environment that fails fast on missing variables
def renderJinja(templateText: str, context: dict[str, Any], rng: random.Random | None = None) -> str:
    env = Environment(undefined=StrictUndefined)                                    # use StrictUndefined environment
    env.globals.update(getLibraryFunctionRegistry(rng))                             # Expose library functions so templates can call them directly if needed
    env.filters["indent_after_newline"] = indentAfterNewline                         # Indent multi-line inserts to match placeholder line

    try:                                                                            # If the raw block is a single function call, execute it directly to preserve inner Jinja
        templateText = applyInlineIndentFilter(templateText)
        strippedText = templateText.strip()
        directCallMatch = re.match(r"^([A-Za-z_]\w*)\((.*)\)$", strippedText)
        if directCallMatch:
            functionRegistry = getLibraryFunctionRegistry(rng)
            if directCallMatch.group(1) in functionRegistry:
                return str(
                    callLibraryFunctionByName(
                        directCallMatch.group(1),
                        directCallMatch.group(2),
                        context,
                        functionRegistry,
                    )
                )

        rendered = env.from_string(templateText).render(context).strip()            # Render the template with the provided context

        functionCallMatch = re.match(r"^([A-Za-z_]\w*)\((.*)\)$", rendered)
        if functionCallMatch:                                                       # If the rendered output is a single function call, execute it
            functionRegistry = getLibraryFunctionRegistry(rng)
            if functionCallMatch.group(1) in functionRegistry:
                return str(
                    callLibraryFunctionByName(
                        functionCallMatch.group(1),
                        functionCallMatch.group(2),
                        context,
                        functionRegistry,
                    )
                )

        return rendered                                                             # Otherwise return the rendered string as-is
    except TemplateSyntaxError as exc:                                              # Map Jinja syntax errors back to the closest template line
        lines = templateText.splitlines()
        badLine = lines[exc.lineno - 1] if exc.lineno and exc.lineno <= len(lines) else templateText
        raise errorAt(badLine) from exc
    except Exception as exc:                                                        # Map other errors (like undefined vars) to the most relevant line
        message = str(exc)
        badLine = message

        undefinedMatch = re.search(r"'(.+?)' is undefined", message)
        if undefinedMatch:                                                          # If undefined variable is reported, try to locate the line that referenced it
            token = undefinedMatch.group(1)
            for candidateLine in templateText.splitlines():
                if token in candidateLine:
                    badLine = candidateLine
                    break

        raise errorAt(badLine) from exc                                             # Raise a normalized error with context for user-facing templates


# ================ deferLibraryCallsInJinja: DEFERS ENGINE CALLS INSIDE {{ }} OR RAW LINES ================
# Replace {{ func(...) }} with a literal token so Jinja doesn't execute engine calls.
# Genuinely had me going insane, I needed so much help from chat
def deferLibraryCallsInJinja(templateText: str, functionRegistry: dict[str, Any]) -> tuple[str, dict[str, str]]:
    def replaceMatch(match: re.Match) -> str:
        funcName = match.group(1)
        args = match.group(2)
        if funcName in functionRegistry:
            return f"__ENGINE_CALL__{funcName}({args})__"
        return match.group(0)

    deferred = re.sub(r"{{\s*([A-Za-z_]\w*)\((.*?)\)\s*}}", replaceMatch, templateText)

    # Replace full-line engine calls so Jinja won't parse inner {{ }} placeholders.
    lineMap: dict[str, str] = {}
    processedLines: list[str] = []
    tokenIndex = 0
    for rawLine in deferred.splitlines():
        stripped = rawLine.strip()
        lineMatch = re.match(r"^([A-Za-z_]\w*)\(\s*(.*)\s*\)\s*;?$", stripped)
        if lineMatch and lineMatch.group(1) in functionRegistry:
            token = f"__ENGINE_LINE_{tokenIndex}__"
            tokenIndex += 1
            lineMap[token] = rawLine
            # Preserve indentation
            indent = rawLine[: len(rawLine) - len(rawLine.lstrip())]
            processedLines.append(f"{indent}{token}")
        else:
            processedLines.append(rawLine)

    return "\n".join(processedLines), lineMap


# ================ restoreLibraryCallsInJinja: RESTORES DEFERRED ENGINE CALLS ================
# For lines that were fully deferred, replace the token with the original line; for inline calls, convert the token back to the function call format.
def restoreLibraryCallsInJinja(renderedText: str, lineMap: dict[str, str]) -> str:
    restored = re.sub(r"__ENGINE_CALL__([A-Za-z_]\w*\(.*?\))__", r"\1", renderedText)
    for token, originalLine in lineMap.items():
        restored = restored.replace(token, originalLine)
    return restored


# ================ evaluateAnswer: EVALUATES EACH ANSWER LINE AS ONE METHOD CALL OR TEXT ================
# e.g. evaluateAnswer("answerLine1\nfuncCall(x)", ctx) -> ["answerLine1", "<func result>"]
# Returns a list of answer strings (even if there is only one)
def evaluateAnswer(answerBlock: str, context: dict[str, Any], rng: random.Random | None = None) -> list[str]:
    # Render full blocks when Jinja control structures are present, then process line-by-line.
    if "{%" in answerBlock and "%}" in answerBlock:
        functionRegistry = getLibraryFunctionRegistry(rng)
        deferredBlock, lineMap = deferLibraryCallsInJinja(answerBlock, functionRegistry)
        renderedBlock = renderJinja(deferredBlock, context, rng)
        renderedBlock = restoreLibraryCallsInJinja(renderedBlock, lineMap)
        statementLines = [line.strip() for line in renderedBlock.splitlines() if line.strip()]
        if not statementLines:
            return []

        answerLines: list[str] = []
        for statementLine in statementLines:
            candidates = generateFromLine(statementLine, context, rng)
            if candidates:
                answerLines.append(candidates[0])

        return answerLines

    statementLines = [line.strip() for line in answerBlock.splitlines() if line.strip()]
    if not statementLines:                                              # No answer content provided
        return []

    answerLines: list[str] = []
    for statementLine in statementLines:                                # Render each line and choose a deterministic candidate
        candidates = generateFromLine(statementLine, context, rng)
        if candidates:
            answerLines.append(candidates[0])                           # For answers, use the first non-empty candidate

    return answerLines                                                  # Return the full list for multi-select support

# ================ evaluateIncorrect: EVALUATES EACH INCORRECT LINE AS ONE METHOD CALL ================
# e.g. evaluateIncorrect("distract()\nwrong()", ctx, correct) -> ["42", "17"]
# Returns a list of incorrect options, skipping duplicates and the correct answer
def evaluateIncorrect(
    incorrectBlock: str,
    context: dict[str, Any],
    correctAnswers: list[str],
    rng: random.Random | None = None,
) -> list[str]:
    if "{%" in incorrectBlock and "%}" in incorrectBlock:                                       # If Jinja control blocks are present, render the whole block then split lines
        functionRegistry = getLibraryFunctionRegistry(rng)
        deferredBlock, lineMap = deferLibraryCallsInJinja(incorrectBlock, functionRegistry)
        incorrectBlock = renderJinja(deferredBlock, context, rng)
        incorrectBlock = restoreLibraryCallsInJinja(incorrectBlock, lineMap)

    statementLines = [line.strip() for line in incorrectBlock.splitlines() if line.strip()]
    if not statementLines:                                                                      # No incorrect content provided lol
        return []

    incorrectPool: list[str] = []
    usedAnswers: set[str] = set(correctAnswers)                                                 # Seed the used set with the correct answers so none appear as incorrect

    for statementLine in statementLines:                                                        # Generate all candidate strings for the line (function call or text)
        candidates = generateFromLine(statementLine, context, rng)
        if not candidates:
            continue
        filteredPool = [candidate for candidate in candidates if candidate not in usedAnswers]  # Filter out used answers, then choose a random remaining option
        if not filteredPool:
            continue
        chosen = rng.choice(filteredPool) if rng else random.choice(filteredPool)

        # Track and store the chosen incorrect option
        incorrectPool.append(chosen)
        usedAnswers.add(chosen)

    return incorrectPool                                                                        # Return the final pool of incorrect answers

# ================ generateFromLine: CALLS ONE LIBRARY METHOD OR RENDERS ONE TEXT LINE ================
# e.g. generateFromLine("UInt(1, 3)", ctx) -> ["2"]
# Returns a list of candidate strings for a single line (may be empty)
def generateFromLine(
    statementLine: str,
    context: dict[str, Any],
    rng: random.Random | None = None,
) -> list[str]:
    methodMatch = re.match(r"^([A-Za-z_]\w*)\(\s*(.*)\s*\)\s*;?$", statementLine)
    if not methodMatch:                                                         # Treat non-call lines as plain text with Jinja rendering support
        dottedMatch = re.match(r"^([A-Za-z_]\w*)(\.[A-Za-z_]\w*)+\s*$", statementLine)
        if dottedMatch:
            resolved = resolveDottedValue(statementLine.strip(), context)
            candidate = str(resolved).strip()
            return [candidate] if candidate else []
        candidate = renderJinja(statementLine, context, rng).strip()
        return [candidate] if candidate else []

    methodName = methodMatch.group(1)
    argumentBody = methodMatch.group(2)

    # Execute the library function referenced by this line (fallback to rendering if not found)
    functionRegistry = getLibraryFunctionRegistry(rng)
    if methodName not in functionRegistry:
        candidate = renderJinja(statementLine, context, rng).strip()
        return [candidate] if candidate else []

    result = callLibraryFunctionByName(methodName, argumentBody, context, functionRegistry)

    if isinstance(result, list):                                                # Normalize list results to a list of non-empty strings
        return [str(item).strip() for item in result if str(item).strip()]

    # Normalize scalar results to a single-item list if non-empty
    candidate = str(result).strip()
    return [candidate] if candidate else []

# ================ generateQuestion: MAIN HIGH-LEVEL API FOR THE FLASK APP ================
# e.g. generateQuestion(fullTemplateText) -> {"question": "...", "answer": "...", "incorrect": [...], "variables": {...}}
# Returns the fully rendered question payload for the app
def generateQuestion(
    templateText: str,
    promptText: str = "",
    feedbackText: str = "",
    seed: int | None = None,
) -> dict[str, Any]:
    if not promptText.strip():
        raise TemplateProcessingError("ERROR at: missing prompt content")
    rng = random.Random(seed) if seed is not None else random.Random()
    # Evaluate variables first so later sections can reference them
    sections = parseSections(templateText)
    context = evaluateVariables(sections.variables, rng)

    # Render each section using the appropriate parser/renderer
    renderedPromptLines = evaluateAnswer(promptText, context, rng)
    renderedQuestion = renderJinja(sections.question, context, rng).strip()
    renderedAnswers = evaluateAnswer(sections.answer, context, rng)
    renderedIncorrect = evaluateIncorrect(sections.incorrect, context, correctAnswers=renderedAnswers, rng=rng)
    renderedFeedbackLines = evaluateAnswer(feedbackText, context, rng)

    # Return the final response payload
    return {
        "prompt": "\n".join(renderedPromptLines).strip(),
        "question": renderedQuestion,
        "answer": renderedAnswers,
        "incorrect": renderedIncorrect,
        "feedback": "\n".join(renderedFeedbackLines).strip(),
    }
