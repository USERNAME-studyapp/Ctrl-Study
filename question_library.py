# Purpose:
# This module defines reusable generation helpers used by the template engine

# Function:
# - Stores generated UInt values with both numeric value and variable display name
# - Generates random UInt values from a provided name and numeric range
# - Provides comparison helpers used inside template expressions
# - Builds incorrect-answer permutations from a formatting template

from __future__ import annotations

from dataclasses import dataclass               # Dataclass is used for readable structured value storage
import itertools                                # Itertools is used for permutation-based answer generation
import random                                   # Random is used for numeric generation and output shuffling
import re                                       # Regex is used to read placeholder names from template text
from typing import Any                          # Any keeps helper signatures flexible for custom future types
from jinja2 import Environment, StrictUndefined # Jinja is used to render formatting strings safely
import supabase_client                          # Supabase client is used for random names from the database


# UNumberValue stores both the value and the variable name seen by users
@dataclass
class UNumberValue:
    value: float
    name: str

    # Converts the object to its numeric string representation
    def __str__(self) -> str:
        return str(self.value)

    # Converts the object to a float for math/comparison use
    def __float__(self) -> float:
        return float(self.value)

    # Converts the object to an integer for math/comparison use
    def __int__(self) -> int:
        return int(self.value)

# UIntValue stores an integer value and inherits numeric behavior
@dataclass
class UIntValue(UNumberValue):
    value: int


# LoopIntValue stores a randomized loop variable definition and its generated iteration values
@dataclass
class LoopIntValue:
    current: int
    start: int
    end: int
    step: int
    name: str
    operator: str
    values: list[int]
    varId: str = ""

    # Converts the object to the loop's current value for template rendering
    def __str__(self) -> str:
        return str(self.current)

    # Converts the object to an integer for math/comparison use
    def __int__(self) -> int:
        return self.current

    # Returns how many loop iterations were generated
    @property
    def iterations(self) -> int:
        return len(self.values)

# ChoiceValue stores a selected option and a comparison-friendly value for template logic
@dataclass
class ChoiceValue:
    text: str
    value: Any

    # Converts the object to its display text for template rendering
    def __str__(self) -> str:
        return self.text

# Name stores a full name with easy template access to each part
@dataclass
class Name:
    first: str
    middle: str
    last: str

    # Converts the object to its display name for template rendering
    def __str__(self) -> str:
        if self.middle:
            return f"{self.first} {self.middle}. {self.last}"
        return f"{self.first} {self.last}"

# ____________________________________________ DATA TYPE HELPERS _________________________________________

# Canonical C++-style data types and their typical sizes (in bytes) for 64-bit environments.
_DATA_TYPES: dict[str, int] = {
    "char": 1,
    "bool": 1,
    "short": 2,
    "int": 4,
    "long": 8,
    "float": 4,
    "double": 8,
}

# ____________________________________________ VALUE GENERATORS _________________________________________

# ================ UInt: CREATES A RANDOM UNSIGNED INTEGER WITH EXPLICIT NAME AND RANGE ================
# Use: UInt(myVar, 4, 10)
def UInt(name: str = "value", minValue: int = 0, maxValue: int = 100) -> UIntValue:
    # Validates range rules for unsigned integer generation
    if minValue < 0 or maxValue < 0 or minValue > maxValue:
        raise ValueError("UInt range must be non-negative and min <= max.")

    # Generates the value and returns a structured UIntValue object
    randomValue = random.randint(minValue, maxValue)
    return UIntValue(value=randomValue, name=name)


# ================ UFloat: CREATES A RANDOM UNSIGNED FLOAT WITH EXPLICIT NAME AND RANGE ================
# Use: UFloat(myVar, 0.0, 10.0, 2)
def UFloat(name: str = "value", minValue: float = 0.0, maxValue: float = 100.0, precision: int | None = 2) -> UNumberValue:
    # Validates range rules for unsigned float generation
    if minValue < 0 or maxValue < 0 or minValue > maxValue:
        raise ValueError("UFloat range must be non-negative and min <= max.")

    # Generates the value and returns a structured UNumberValue object
    randomValue = random.uniform(minValue, maxValue)
    if precision is not None:
        randomValue = round(randomValue, precision)
    return UNumberValue(value=randomValue, name=name)

# ================ LoopInt: CREATES A RANDOMIZED LOOP VARIABLE CONFIGURATION ================
# Use: LoopInt(i, 0, 4, 8, 20, 1, 3, True)
# Args: LoopInt(name, startMin, startMax, endMin, endMax, stepMin, stepMax, allowDecrement)
def LoopInt(
    name: str = "i",
    startMin: int = 0,
    startMax: int = 5,
    endMin: int = 6,
    endMax: int = 15,
    stepMin: int = 1,
    stepMax: int = 3,
    allowDecrement: bool = False,
) -> LoopIntValue:
    
    # Validates bound ranges
    if startMin > startMax:
        raise ValueError("LoopInt startMin must be <= startMax.")
    if endMin > endMax:
        raise ValueError("LoopInt endMin must be <= endMax.")
    if stepMin <= 0 or stepMax <= 0 or stepMin > stepMax:
        raise ValueError("LoopInt step bounds must be positive and stepMin <= stepMax.")

    # Tries multiple random combinations until a valid non-empty loop is found
    for _ in range(200):
        start = random.randint(startMin, startMax)
        end = random.randint(endMin, endMax)
        stepMagnitude = random.randint(stepMin, stepMax)

        # Chooses increment/decrement step direction
        stepChoices = [stepMagnitude]
        if allowDecrement:
            stepChoices.append(-stepMagnitude)
        step = random.choice(stepChoices)

        # Builds candidate values and skips empty loops
        if step == 0:
            raise ValueError("LoopInt step cannot be zero.")
        values = list(range(start, end, step))
        if not values:
            continue

        # Sets loop comparison operator for easier template generation
        operator = "<" if step > 0 else ">"

        # Returns structured loop value once valid
        return LoopIntValue(
            current=values[0],
            start=start,
            end=end,
            step=step,
            name=name,
            operator=operator,
            values=values,
        )

    # Fails clearly when no valid loop could be created from provided constraints
    raise ValueError("LoopInt could not generate a non-empty loop with the provided bounds.")

# ================ nameGen: GENERATES A RANDOM FULL NAME OBJECT ================
# Use: nameGen()
def nameGen() -> Name:
    record = supabase_client.FetchRandomName()
    if not record:
        raise ValueError("nameGen could not fetch a name from the database.")

    first = str(record.get("FirstName", "")).strip()
    middle = str(record.get("MiddleInitial", "")).strip()
    last = str(record.get("LastName", "")).strip()

    if not first or not last:
        raise ValueError("nameGen received an incomplete name record.")

    middleInitial = middle[0].upper() if middle else ""
    return Name(first=first, middle=middleInitial, last=last)

# ================ charGen: GENERATES A SIMPLE LOWERCASE LETTER ================
# Use: charGen(var1.name) -> "a" or "b" or ... "z"; for simple variable names or character-based questions
def charGen(*exclude: str) -> str:
    excluded = {c.lower() for c in exclude if len(c) == 1}              # normalize exclusion set
    pool = [chr(i) for i in range(97, 123) if chr(i) not in excluded]   # builds pool of lowercase letters excluding any in the exclusion set
    if not pool:                                                        # if pool empty, raise error
        raise ValueError("charGen exclusion list removes all letters.")
    return random.choice(pool)                                          # returns a random letter from the remaining pool

# ================ greaterThan: RETURNS A RANDOM INTEGER THAT IS STRICLY GREATER THAN THE BASE ================
# Use: greaterThan(myVar) or greaterThan(5)
def greaterThan(base: Any) -> Any:
    if isinstance(base, UNumberValue):                                           # Supports numeric library values (int or float)
        baseValue = float(base.value)
        if isinstance(base.value, float) and not base.value.is_integer():
            return random.uniform(baseValue + 0.1, baseValue + 10.0)
        return random.randint(int(baseValue) + 1, int(baseValue) + 10)

    baseValue = float(base)
    if isinstance(base, float) and not base.is_integer():
        return random.uniform(baseValue + 0.1, baseValue + 10.0)
    return random.randint(int(baseValue) + 1, int(baseValue) + 10)


# ================ lessThan: RETURNS A RANDOM INTEGER THAT IS STRICLY LESS THAN THE BASE ================
# Use: lessThan(myVar) or lessThan(5)
def lessThan(base: Any) -> Any:
    if isinstance(base, UNumberValue):                                           # Supports numeric library values (int or float)
        baseValue = float(base.value)
        if isinstance(base.value, float) and not base.value.is_integer():
            if baseValue <= 0.1:
                return 0.0
            return random.uniform(0.0, baseValue - 0.1)
        if baseValue <= 1:
            return 0
        return random.randint(0, int(baseValue) - 1)

    baseValue = float(base)
    if isinstance(base, float) and not base.is_integer():
        if baseValue <= 0.1:
            return 0.0
        return random.uniform(0.0, baseValue - 0.1)
    if baseValue <= 1:
        return 0
    return random.randint(0, int(baseValue) - 1)


# ================ choose: RETURNS ONE LABELED OPTION FOR TEMPLATE CONDITION LOGIC ================
# Use: whichWay = choose(("does not", False), ("does", True))
def choose(*options: tuple[Any, Any]) -> ChoiceValue:
    if not options:                                                             # Validates that at least one option is provided
        raise ValueError("choose expects at least one (text, value) option.")

    normalized: list[ChoiceValue] = []                                          # Normalizes each option to a (text, value) pair
    for option in options:
        if not isinstance(option, tuple) or len(option) != 2:
            raise ValueError("choose expects options shaped like (text, value).")
        text, value = option
        normalized.append(ChoiceValue(text=str(text), value=value))

    return random.choice(normalized)                                            # Returns one random option for use in templates

# ================ randomDataType: RETURNS A RANDOM DATA TYPE STRING ================
# Use: randomDataType() or randomDataType("double", "float")
def randomDataType(*exclude: str) -> str:
    if not _DATA_TYPES:
        raise ValueError("randomDataType has no available data types.")

    excluded = {str(value).strip().lower() for value in exclude if str(value).strip()}
    pool = [key for key in _DATA_TYPES.keys() if key.lower() not in excluded]

    if not pool:
        raise ValueError("randomDataType exclusion list removes all data types.")

    return random.choice(pool)


# ____________________________________________ VALUE METHODS _________________________________________

# ================ lines: JOINS MULTIPLE STRINGS WITH NEWLINES ================
# Use: lines("line one", "line two") -> "line one\nline two"
def lines(*parts: Any) -> str:
    if not parts:                                                       # validates at least one part is provided
        raise ValueError("lines expects at least one string.")

    return "\n".join(str(part) for part in parts)                       # joins parts with newline characters

# ================ sizeOfCalc: RETURNS TOTAL SIZE FOR A TYPE AND COUNT ================
# Use: sizeOfCalc("double", 20)
def sizeOfCalc(typeName: str, count: int) -> int:
    if not isinstance(typeName, str) or not typeName.strip():
        raise ValueError("sizeOfCalc expects a non-empty type name.")
    if not isinstance(count, int) or count < 0:
        raise ValueError("sizeOfCalc expects a non-negative integer count.")

    key = typeName.strip().lower()
    if key not in _DATA_TYPES:
        raise ValueError(f"sizeOfCalc does not recognize type: {typeName}")

    return _DATA_TYPES[key] * count

# ================ randomLoop: CREATES A DYNAMIC LOOP RENDER GIVEN A LOOP INTEGER AND BODY (C++ ONLY FOR NOW!!!!) ================
# Use: randLoopVar = randomLoop(loopIntValue, loopBodyString1, loopBodyString2, ...)
def randomLoop(loopInt: LoopIntValue, *bodyLines: str) -> str:
    # Validates loop variable type for predictable rendering.
    if not isinstance(loopInt, LoopIntValue):
        raise ValueError("randomLoop expects a LoopIntValue as the first argument.")

    # Normalizes body lines into a list of individual lines to indent consistently.
    flattenedBody: list[str] = []
    for line in bodyLines:
        if not isinstance(line, str):
            flattenedBody.append(str(line))
            continue
        for subLine in line.splitlines():
            flattenedBody.append(subLine)

    # Prepares operator and step syntax for C++ loop headers.
    comparisonOperator = loopInt.operator
    stepMagnitude = abs(loopInt.step)
    stepOperator = "+=" if loopInt.step >= 0 else "-="

    # Builds the loop body with consistent indentation.
    if not flattenedBody:
        renderedBody = "    "
    else:
        renderedBody = "\n".join(f"    {line}" for line in flattenedBody)

    # Randomly chooses between for-loop and while-loop structures.
    loopStyle = random.choice(["for", "while"])

    if loopStyle == "for":
        # Renders a C++ for-loop with the loop variable and bounds.
        return (
            f"for (int {loopInt.name} = {loopInt.start}; "
            f"{loopInt.name} {comparisonOperator} {loopInt.end}; "
            f"{loopInt.name} {stepOperator} {stepMagnitude}) {{\n"
            f"{renderedBody}\n"
            "}"
        )

    # Renders a C++ while-loop with explicit initialization and step.
    return (
        f"int {loopInt.name} = {loopInt.start};\n"
        f"while ({loopInt.name} {comparisonOperator} {loopInt.end}) {{\n"
        f"{renderedBody}\n"
        f"    {loopInt.name} {stepOperator} {stepMagnitude};\n"
        "}"
    )

# ================ combinations: RENDERS UNIQUE PERMUTATIONS FROM A JINJA FORMAT STRING AND SOURCE VALUES ================
# Use: combinations("{{ x }} {{ y }}", var1, var2, ...)
def combinations(formatString: str, *values: Any, exclude: str | None = None) -> list[str]:
    placeholders = re.findall(r"{{\s*([A-Za-z_]\w*)\s*}}", formatString)        # Reads placeholder names like x, y, z from blocks like {{ x }}

    uniquePlaceholders: list[str] = []
    for name in placeholders:                                                   # Keeps placeholders unique while preserving appearance order
        if name not in uniquePlaceholders:
            uniquePlaceholders.append(name)

    if not uniquePlaceholders:                                                  # Returns an empty list when formatString has no placeholders
        return []

    # Prepares strict Jinja rendering so missing keys throw errors
    env = Environment(undefined=StrictUndefined)
    template = env.from_string(formatString)

    # Generates each permutation and collects unique rendered text
    rendered: set[str] = set()
    flattenedValues: list[Any]
    if len(values) == 1 and isinstance(values[0], (list, tuple)):
        flattenedValues = list(values[0])
    else:
        flattenedValues = list(values)

    stringValues = [str(value) for value in flattenedValues]
    for combo in itertools.permutations(stringValues, len(uniquePlaceholders)):
        mapping = dict(zip(uniquePlaceholders, combo))
        text = template.render(mapping).strip()
        if text and text != exclude:
            rendered.add(text)

    # Randomizes final ordering so output varies per generation
    results = list(rendered)
    random.shuffle(results)
    return results

# ================ loopPrint: RENDERS A FORMAT STRING USING NESTED LOOP VARIABLE ITERATION ORDER ================
# Use: loopPrint(formatJinjaString, loopInt1, loopInt2, ...)
def loopPrint(formatString: str, *loopVars: Any) -> str:
    if len(loopVars) > 4:                                                   # Validates max loop count to be less than 4 (there's no way there's going to be a question with 5 and greater nested loops right??)
        raise ValueError("loopPrint supports at most 4 LoopIntValue arguments.")

    for loopVar in loopVars:                                                # Validates loop var types for predictable nested-loop behavior
        if not isinstance(loopVar, LoopIntValue):
            raise ValueError("loopPrint expects LoopIntValue arguments after formatString.")

    env = Environment(undefined=StrictUndefined)
    template = env.from_string(formatString)                                # Builds strict Jinja renderer for every loop iteration render step

    if not loopVars:                                                        # Handles the no-loop case by rendering the template a single time
        return template.render({})

    valueLists = [loopVar.values for loopVar in loopVars]                   # Collects each loop's values list; rightmost loop should increment fastest
    renderedPieces: list[str] = []

    for valueTuple in itertools.product(*valueLists):                       # Iterates in true nested-loop order using the CARTESIAN PRODUCT LOL
        for index, currentValue in enumerate(valueTuple):                   # Updates current value for each loop variable in this iteration state
            loopVars[index].current = currentValue

        renderContext: dict[str, Any] = {}
        for loopVar in loopVars:                                            # Exposes loop variables by their declared names (and template variable IDs if present).
            renderContext[loopVar.name] = loopVar
            if loopVar.varId:
                renderContext[loopVar.varId] = loopVar

        renderedPieces.append(template.render(renderContext))               # Renders this single nested-loop iteration and stores the output

    for loopVar in loopVars:                                                # Sets loop variable state to end after iteration sequence is finished
        loopVar.current = loopVar.end

    return "".join(renderedPieces)                                          # Returns final concatenated output across all nested iterations
