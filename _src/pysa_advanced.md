---
id: pysa-advanced
title: Advanced Topics
sidebar_label: Advanced Topics
---

This page documents less straightforward bits of Pysa.

## Conditional models based on Python version

Pysa models support if conditions but only for version comparisons for the python
version used to run pysa. This allows for conditional parsing of models and allows
different models to be used for different versions of python.

```python
if sys.version == (3,9,0):
    def module.foo(): ...
else:
    def module.bar(): ...
```
In this example, the first model will only be parsed and honoured if the python
version in the system or virtual environment from which Pysa is run is equal
to "3.9.0". In all other conditions, the second model will be parsed and honoured.

sys.version is the only allowed left hand expression and the right hand expression
has to be a tuple of integers of the form (major, minor, micro). Only the major
version number is required and the other two are optional.

The comparison operators supported include '==' (equal to), '!=' (not equal to),
'&lt;' (less than), '&gt;' greater than, '&lt;=' (less than or equal to), and
'&gt;=' (greater than or equal to).

If conditions can also be nested inside one another and follow the same behavior
as python if conditions.

## Obscure models

When Pysa does not have enough information about a function or method, it will
make basic assumptions about its behavior. This is referred to as an **obscure
model**. Most notably, it assumes that the function or method propagates the
taint from its arguments to its return value.

This usually happens when Pysa doesn't know about the callee of a function call:

```python
def foo(f: Any):
    x = input()
    y = f(x) # no information about `f`, y will be considered tainted.
    eval(y)
```

Functions and methods defined in type stubs or in a different language (for
instance, in C or C++ binding) will also be treated as obscure models.

To prevent a function or method to be marked as obscure, one can use the
`@SkipObscure` taint annotation in a `.pysa` file:

```python
@SkipObscure
def module.foo(): ...
```

## Parameter and return path

When writing a model for a source, the `ReturnPath` annotation allows to specify
which index or attribute of the returned value is tainted. For instance:

```python
def only_attribute_foo_tainted() -> TaintSource[Test, ReturnPath[_.foo]]: ...
```

Similarly, the `ParameterPath` annotation allows to specify which index or attribute
of an argument leads to a sink. For instance:

```python
def only_arg_dot_bar_is_sink(arg: TaintSink[Test, ParameterPath[_.bar]]): ...
```

### Access path definition

The `ParameterPath` and `ReturnPath` annotation takes an **access path** as an argument.
An access path starts with an underscore `_` which represents the whole argument or
return value (depending on the context). The underscore can be followed by attribute
accesses (e.g, `_.foo.bar`) and index accesses (e.g, `_["foo"][0]["bar"]`), or a
combination of both (e.g, `_.foo[0]`).

In addition to these, three special calls can be used: `.all()`, `.keys()` and
`.all_static_fields()`.

#### all()

`.all()` is used to represent that any index might be tainted. This is usually when
the index cannot be known statically. For instance:

```python
def foo(i: int):
  i = random.randint(0, 100)
  return {i: source()}
```

This can be represented by the model:
```python
def foo(): TaintSource[Test, ReturnPath[_.all()]]: ...
```

#### keys()

`.keys()` is used to represent that any key of the dictionary might be tainted.
For instance:

```python
def foo():
  return {source(): 0}
```

This can be represented by the model:
```python
def foo(): TaintSource[Test, ReturnPath[_.keys()]]: ...
```

#### all_static_fields()

`.all_static_fields()` is used to mark all statically-known attributes of the
given parameter as a source or sink. The set of attributes is determined using
the type annotation of the parameter. If the parameter is not annotated or that
we could not find any attributes, the whole parameter will be marked as a source
or sink instead.

For instance:
```python
class A:
  x: str
  y: str

def foo(a: A): ...
```

Using the following model:
```python
def foo(a: TaintSink[Test, ParameterPath[_.all_static_fields()]]): ...
```

This will add a sink on `a.x` and `a.y`.

In general, we recommend to **mark the whole parameter** as a source or sink.
This feature is **only useful** for power users that post process the result of
the analysis and extract leaf ports. It is also very **computationally expensive**.

### Taint In Taint Out

`ParameterPath` and `ReturnPath` can also be used to give more information about
a propagation. For instance:

```python
def foo(arg):
  return {"a": arg["b"][42]}
```

This can be represented by the model:
```python
def foo(arg: TaintInTaintOut[ParameterPath[_["b"][42]], ReturnPath[_["a"]]]): ...
```

Note that Pysa will automatically infer propagations if it has access to the body
of the function. Writing taint-in-taint-out models should rarely be required.

When using the `Updates` annotation, the annotation `UpdatePath` is used instead
of `ReturnPath`. For instance:

```python
def MyClass.updates_foo(self, x: TaintInTaintOut[Updates[self], UpdatePath[_.foo]]): ...
```

## Collapsing on taint-in-taint-out

Collapsing (also called taint broadening) is an over-approximation performed by
the taint analysis for correctness or performance reasons. After applying collapsing,
Pysa considers that a whole object or variable is tainted when only some attributes
or keys were initially tainted.

The most common causes for taint collapsing are:
* Taint goes through an [obscure model](#obscure-models), when it does not have
the body of the callee; Pysa must assume anything could get tainted, for correctness.
* The number of tainted attributes or keys hits a [threshold](#tune-the-taint-tree-width-and-depth).
To prevent the analysis from blowing up by tracking too many values, Pysa assumes the whole object is tainted.

Whenever collapsing happens, Pysa will add the [broadening feature](pysa_features.md#broadening-feature) on
the taint flow, which can help discard false positives in post processing.

When specifying a [taint propagation](pysa_basics.md#taint-propagation) in a `.pysa` file,
the propagation will collapse the taint by default. For instance:

```python
def tito(arg: TaintInTaintOut): ...
```

```python
def foo():
  x = {"a": source()}
  y = tito(x) # Only `x['a']` is tainted, but `y` gets tainted.
  sink(y) # Issue since `y` is tainted
  sink(y['b']) # Also an issue, because taint is propagated from `y` to `y['b']`.
```

If the function is known to preserve the structure of the argument, the `NoCollapse`
annotation can be used to disable collapsing. For instance:

```python
def tito(arg: TaintInTaintOut[NoCollapse]): ...
```

This would remove both issues from the previous example.

Note that this can be used in combination with [`ParameterPath` and `ReturnPath`](#parameter-and-return-path).

## Tainting Specific `kwargs`

Sometimes, a function can have potential sinks mixed together with benign
parameters in the keyword arguments (`kwargs`) that it accepts. In these cases,
tainting the whole `kwargs` variable will result in false positives when tainted
data flows into a benign `kwarg`. Instead, for a function like this:

```python
def eval_and_log(**kwargs):
    eval(kwargs["eval"])
    logging.debug(kwargs["log"])
```

We can lie a bit in our `.pysa` file, and break out the dangerous argument for
tainting:

```python
def eval_and_log(*, eval: TaintSink[RemoteCodeExecution], **kwargs): ...
```

This allows us to catch flows only into the `eval` keyword argument.

## Instance attributes versus class attributes

Models can specify sources and sinks on attributes, following the type annotation
syntax:

```python
django.http.request.HttpRequest.GET: TaintSource[UserControlled]
```

Any access to `request.GET` will be tainted when `request` is an instance of
`HttpRequest` or any of its children. However, note that the access to the class
attribute (i.e, `HttpRequest.GET`) won't be considered tainted.

To specify sources and sinks on class attributes, use the `__class__` prefix:

```python
django.http.request.HttpRequest.__class__.GET: TaintSource[UserControlled]
```

To specify a source on both the class attribute and instance attribute, simply
use both lines.

## Literal String Sources And Sinks

Some security vulnerabilities are best captured by modeling strings of a given
form flowing to dangerous functions, or format strings that match a pattern getting
tainted data passed in.

To mark all literal strings matching a pattern as sources, you first need to add a
regular expression corresponding to the pattern to your `taint.config`:

```json
{
  "sources": [
    {
      "name": "IPAddress"
    }
  ],
  "implicit_sources": {
     "literal_strings": [
       {
         "regexp": "\\d{1,3}(\\.\\d{1,3})+",
         "kind": "IPAddress",
         "description": "String that looks like an IP address."
       }
     ]
  }
}
```

With this regex in place, whenever Pysa sees a string such as `123.456.789.123`, it will flag it
as a taint source with the kind `IPAddress`.

```python
def test() -> None:
    ip_address = "123.456.789.123"
    dont_pass_an_ip_address(ip_address) # Pysa will now flag this.
```

The converse of supporting literal strings as sinks is also supported, for data flowing into a tainted string. The
syntax allows you to model data being used to format strings, like f-strings, manual string formatting, the string `format()` method, and printf-style string formatting with `%`.

Template strings and manual string formatting with more than two subexpressions are not yet supported.

To add a literal sink, first add the literal_sink to your configuration

```json
{
  "sinks": [
    { "name": "MayBeRendered" },
    { "name": "MayBeSQL" }
  ],
  "implicit_sinks": {
     "literal_strings": [
       {
         "regexp": "^<.*>$",
         "kind": "MayBeRendered",
         "description": "Indicates a string whose contents may be rendered."
       },
       {
         "regexp": "^SELECT *.",
         "kind": "MayBeSQL",
         "description": "Indicates a string whose contents may be a SQL query."
       }

     ]
  }
```

Now, Pysa will treat any values flowing into a each of the following as a regular sink:

```python
def may_render(parameter: str) -> None:
    result = f"<content={parameter}>"
    result = "<content={}>".format(parameter)
    result = "<content%s>" % (parameter,)
```
As well as values flowing into each of these as a regular sink:
```python
def build_sql_query(columns: str) -> None:
    result = f"SELECT {columns} FROM users;"
    result = "SELECT {} FROM users;".format(columns)
    result = "SELECT %s FROM users" % (columns,)
    result = "SELECT " + columns + " FROM users;"
```

Note that string literal sinks have some limitations. For instance, they cannot catch issues if the string literal is stored in a temporary variable (e.g., `x = "SELECT {}"; x.format(input)`). We recommend using string combine rules instead (see below).

## Combined Source Rules

Some security vulnerabilities are better modeled as *multiple* sources reaching
a sink. For example, leaking credentials via `requests.get` could be modeled as
user controlled data flowing into the `url` parameter and credentials flowing
into the `params` parameter. These flows can be modeled by *combined source
rules*.

Sources for combined source rules are declared as normal in `taint.config`.
Sinks, however, need to be unique to the combined source rule and are declared inside
the rule definition. The rule itself is declared in the `combined_source_rules`
top level entry. The rule lists all the same things as a regular rule, but also ties
labels to its sources:

```json
{
  "sources": [
    { "name": "UserControlled" },
    { "name": "Credentials" }
  ],
  "combined_source_rules": [
    {
       "name": "Credentials leaked through requests",
       "sources": { "url": "UserControlled", "creds": "Credentials" },
       "partial_sink": "UserControlledRequestWithCreds",
       "code": 1,
       "message_format": "Credentials leaked through requests",
       "main_trace_source": "url",
    }
  ]
}
```

Sources are declared as normal in `.pysa` files. Instead of specifying sinks
with a `TaintSink` annotation, however, `PartialSink` annotations are used to
specify where each source needs to flow for the combined source rule. These
`PartialSink` must reference the labels that were declared in
`multi_sink_labels`:

```python
def requests.api.get(
  url: PartialSink[UserControlledRequestWithCreds[url]],
  params: PartialSink[UserControlledRequestWithCreds[creds]],
  **kwargs
): ...
```

With the above configuration, Pysa can detect cases where `UserControlled` flows
into `url` and `Credentials` flow into `params` *at the same time*.

The optional attribute `main_trace_source` can be used to specify which flow should be shown as the main flow in the SAPP UI. For example, in the above rule, the flow from source `UserControlled` to sink `UserControlledRequestWithCreds` is the main flow.

The SAPP UI only shows a single flow at a time. However, an issue for a combined source rule corresponds to two flows. For example, for the above rule, an issue is filed only if there exist
- One flow from source `UserControlled` to sink `UserControlledRequestWithCreds`, and
- Another flow from source `Credentials` to sink `UserControlledRequestWithCreds`.

For combined source issues, Pysa will always show the main flow, and provide the secondary flow as a subtrace that can be expanded in the UI.

When attribute `main_trace_source` is missing, Pysa treat the sources under the first tag as the main sources.

## String Combine Rules

It is sometimes useful to detect data tainted with a source (e.g., `UserControlled` data) that is incorporated into a suspicious looking string (e.g., a string that looks like a SQL query). Detecting such a pattern is useful, because it allows Pysa to detect dynamic creation of SQL queries which could lead to SQL injection, even if the code under analysis is using a SQL framework that Pysa does not have models for.

To detect such flows, one can specify a variant of [combined source rules](#combined-source-rules), called string combine rules, to detect when the suspicious string (identified via regex match) and the other configured source both flow into string formatting call sites (such as calling `str.__add__`, `str.__mod__`, `str.format` or constructing f-strings).

For example, to detect flows from source `UserControlled` to sink `StringMayBeSQL`, one should specify the following contents in the taint configuration file, where `UserControlled` is declared as a main source and `StringMayBeSQL` is declared as a secondary source:
```python
{
  "sources": [
    { "name": "UserControlled" },
    { "name": "StringMayBeSQL" }
  ],
  "implicit_sources": {
    "literal_strings": [
      {
        "regexp": "SELECT.*",
        "kind": "StringMayBeSQL",
        "comment": "matches a SQL statement"
      }
    ]
  },
  "string_combine_rules": [
    {
       "name": "User controlled data flows into potential SQL strings",
       "main_sources": "UserControlled",
       "secondary_sources": "StringMayBeSQL",
       "partial_sink": "UserControlledDataAndStringMayBeSQL",
       "code": 4324,
       "message_format": "User controlled data flows into potential SQL strings"
    }
  ]
}
```
As shown above, one needs to additionally specify a (unique) partial sink kind (such as `UserControlledDataAndStringMayBeSQL`), which will be automatically introduced onto the actual arguments at string formatting call sites.

The above rule enables catching the following flows:
```python
def issue():
  uc = user_controlled()
  f"SELECT {uc} FROM async_query"
  "SELECT " + uc + " FROM async_query"
  "SELECT %s FROM async_query" % uc
  "SELECT {} FROM async_query".format(uc)
```

Note that the string combine rules are strictly more powerful than the feature of implicit literal string sinks.
That is, any flow that can be detected via implicit literal string sinks can also be detected via string combine rules, but not vice versa.
Hence, we recommend using the string combine rules.

## Prevent Inferring Models with `SkipAnalysis`

In addition to the models defined in `.pysa` files, Pysa will infer models for
functions based what sources, sinks, etc. they call in their body. The
`SkipAnalysis` annotation can be used to prevent Pysa from inferring models, and
instead force it to use only the user defined models for determining taint flow:

```python
@SkipAnalysis
def qualifier.dont_generate_models(argument): ...
```

`SkipAnalysis` can be applied at the class level as a shorthand to prevent pysa
from infering models for all functions in a class:

```python
class skip_analysis.SkipMe(SkipAnalysis): ...
```

## Ignoring overrides

When a method is called on a base class, Pysa has to assume that that call could
actually invoke any subclass methods that override the base class's method. For
heavily overriden methods, this can lead to both performance impacts and false
positives. When running Pysa, you may see messages such as this in the output:

```
2020-09-02 09:25:50,677 WARNING `object.__init__` has 106 overrides, this might slow down the analysis considerably.
```

The above message indicates that 106 subclasses of `object` have overridden
`__init__`. If Pysa sees taint flowing into `object.__init__`, then it will
treat all 106 overrides of `object.__init__` as also receiving that taint.

The `@SkipOverrides` decorator can be applied to deal with false positives or
performance issues from having too many overrides on a given function:

```python
@SkipOverrides
def object.__init__(self): ...
```

This annotation will cause Pysa not to propagate taint into to and from
overridden methods on subclasses, when analyzing functions that call the
overriden method on the base class.

`maximum_overrides_to_analyze` can be added the the `options` block of
`taint.config` to limit the number of overrides that Pysa will analyze:

```json
{
  "sources": [],
  "sinks": [],
  "features": [],
  "rules": [],
  "options": {
    "maximum_overrides_to_analyze": 60
  }
}
```

This option can also be provided in the command line, using
`--maximum-overrides-to-analyze`.

This can speed up the analysis, but it will lead to false negatives, because
Pysa will only propagate taint to or from 60 (in the case of the above example)
overriden methods on subclasses. The remaining overriding methods will be
ignored and treated as if they weren't actually overriding the base class
method.

By default, Pysa skips overrides on some functions that are typically
problematic. You can find the full list of default-skipped functions in
[`stubs/taint/skipped_overrides.pysa`](https://github.com/facebook/pyre-check/blob/main/stubs/taint/skipped_overrides.pysa)

## Limit the trace length for better signal and performance

By default, Pysa will find all flows from sources to sinks matching a rule.
This can lead to very long traces which are hard to understand and tend to be
false positives. This also brings down the performance a lot.

Pysa provides a `--maximum-trace-length <integer>` command line argument which
limits the length of traces that it finds. In general, this will also make Pysa
faster.

This option can also be added in the `taint.config` as follows:

```json
{
  "sources": [],
  "sinks": [],
  "features": [],
  "rules": [],
  "options": {
    "maximum_trace_length": 20
  }
}
```

Note that this is not a silver bullet and that this might hide security
vulnerabilities. Use it with caution.

## Limit the tito depth for better signal and performance

Pysa automatically infers when a function propagate the taint from one argument
to its return value. This is called tito, for "Taint In Taint Out". In practice,
infering it can be very expensive since the taint can go through an arbitrary
number of hops (i.e, depth).

For instance:

```python
def foo(x):
  return x
def bar(x):
  return foo(x)
def baz(x):
  return bar(x)
```

In this example, `baz` propagates the taint on its argument to the return value
using 3 hops.

Pysa provides a `--maximum-tito-depth <integer>` command line argument which
limints the depth of inferred propagations. In combination with the trace length
limit, this usually makes Pysa faster.

This option can also be added in the `taint.config` as follows:

```json
{
  "sources": [],
  "sinks": [],
  "features": [],
  "rules": [],
  "options": {
    "maximum_tito_depth": 20
  }
}
```

## Decorators

By default, Pysa does not generally understand decorators, and will treat a call to a decorated function as an obscure call.

This will usually lead to false negatives if the decorated functions has sources or sinks. For instance:
```python
def identity(f: Callable[[str], None]) -> Callable[[str], None]:
  return f

@identity
def decorated_sink(x: str) -> None:
  sink(x)

decorated_sink(source()) # False negative, issue will NOT be found!
```

This also leads to false negatives if the decorator adds a flow to a sink. For instance:
```python
def with_sink(f: Callable[[str], None]) -> Callable[[str], None]:
  def inner(x: str) -> None:
    sink(x)
    f(x)

  return inner

@with_sink
def foo(x: str) -> None:
  print(x)

foo(source()) # False negative, issue will NOT be found!
```

Since the call to a decorated function is treated as an obscure call, it will conservatively propagate taint through decorated function:
```python
def identity(f: Callable[[str], str]) -> Callable[[str], str]:
  return f

@identity
def decorated(x: str) -> str:
  # Whatever happens here will not be considered at the call site.
  return 'hello %s' % x

sink(decorated(source())) # Issue is properly found.
```

Pysa provides a few ways to deal with these limitations.

## Ignoring decorators

Pysa can entirely ignore a decorator, as if it was not present in the source code. This can be done safely when the decorator does not change the signature of the decorated function (i.e, it does not add or remove parameters).

To ignore a decorator, use the `@IgnoreDecorator` annotation in a `.pysa` file:
```python
@IgnoreDecorator
def module.decorator(): ...
```

## Inlining decorators

Pysa can try to inline decorators into decorated functions before analyzing them. This can be enabled with the `--inline-decorators` flag.

Inlining will take the code of the decorator and copy it within the decorated function. For instance:
```python
def my_decorator(f: Callable[[int], int]) -> Callable[[int], int]:
  def inner(x: int) -> int:
    before(x)
    result = f(x)
    after(x)
    return result

  return inner

@my_decorator
def decorated(x: int) -> int:
  return x + 1
```

Will be inlined as:
```
def decorated(x: int) -> int:
  before(x)
  result = x + 1
  after(x)
  return result
```

### Prevent Inlining Decorators with `SkipDecoratorWhenInlining`

Decorator inlining comes at the cost of increasing the analysis time and also increasing the lengths of traces. If you would like to prevent certain decorators from being inlined, you can mark them in your `.pysa` file using `@SkipDecoratorWhenInlining`:

```python
# foo.pysa
@SkipDecoratorWhenInlining
def foo.decorator_to_be_skipped(f): ...
```

```python
# foo.py
@decorator_to_be_skipped
def bar(x: int) -> None:
  pass
```

This will prevent the decorator from being inlined when analyzing `bar`. Note that we use `@SkipDecoratorWhenInlining` on the decorator that is to be skipped, not the function on which the decorator is applied.

Unfortunately, this will lead back to false negatives as described earlier.

For instance:
```python
@decorator_to_be_skipped
def bar(x: int) -> None:
  sink(x)

bar(source()) # False negative, issue will NOT be found!
```

## Single trace sanitizers with `@SanitizeSingleTrace`

Sanitizers, as described in the [Overview](pysa_basics.md), are applied in both
the forward (i.e source) trace and backward (i.e sink) trace.

For instance, with the given `.pysa` file:

```python
@Sanitize(TaintInTaintOut[TaintSink[RemoteCodeExecution]])
def shlex.quote(x): ...
```

And the following Python code:

```python
import subprocess
from shlex import quote

def quoted_input():
  x = input() # source 'UserControlled'
  y = quote(x)
  return y

def echo(argument):
  subprocess.run(f'/bin/echo {argument}', shell=True) # sink 'RemoteCodeExecution'

def issue():
  x = quoted_input() # source trace: input -> quoted_input -> issue
  echo(x) # sink trace: issue -> echo -> subprocess.run
```

Pysa will NOT find an issue here, as expected.
This is because during the propagation of the 'UserControlled' source in the
forward trace, pysa remembers that it was sanitized for the sink 'RemoteCodeExecution'.

However, Pysa provides a simpler version of sanitizers, which only sanitizes in the
forward trace or the backward trace:

```python
@SanitizeSingleTrace(TaintSource)
def f(): ...

@SanitizeSingleTrace(TaintSource[UserControlled])
def g(): ...

@SanitizeSingleTrace(TaintSink)
def h(): ...

@SanitizeSingleTrace(TaintSink[RemoteCodeExecution])
def i(): ...
```

These sanitizers are a lot cheaper and could save analysis time. However, these
might introduce false positives, so we recommend to use the default sanitizers.

## Filtering the call graph with `@Entrypoint`

By default, Pysa will analyze the entire call graph of your program. This can lead to longer analysis times for larger programs, especially when you'd only like to perform analysis on specific parts of the program. This decorator will mark a specified function and the functions it calls as the only functions to be analyzed.

Note: the flag `--limit-entrypoints` must be passed to `pyre analyze` for call graph filtering to occur, even if the `@Entrypoint` decorator is present. This allows for call graph filtering to be easily enabled or disabled without editing your `.pysa` files.

If you have the following Python file:

```python
class MyClass:
  def class_entrypoint():
    taint_sink(taint_source())

def my_bad_func_1():
  taint_sink(taint_source())

def my_bad_func_2():
  taint_sink(taint_source())

def func_entrypoint():
  my_bad_func_1()

def main():
  func_entrypoint()
  my_bad_func_2()
  MyClass().class_entrypoint()

main()
```

And the following `.pysa` file:

```python
@Entrypoint
def my_file.MyClass.class_entrypoint(): ...

@Entrypoint
def func_entrypoint(): ...
```

Then issues will be found for taint in calls to `class_entrypoint` and `my_bad_func_1`, but not `my_bad_func_2`, since it isn't called by a function marked by an `@Entrypoint`.

## Taint In Taint Out Transforms

Taint in taint out transforms can be used to capture more precise flows.

As an example:
```python
def read_file(path):
  with open(path, "r") as f:
    content = f.read()
  return content
```
Without taint in taint transforms we can write a rule that captures a `UserControlled` path is `read`. Such a rule can be made much higher signal if we can detect that `content` is also `ReturnedToUser`. We can use taint in taint out transforms to stitch the two flows together. We mark `read` with a taint in taint out transform `FileRead`, and the rule becomes `UserControlled -> FileRead -> ReturnedToUser`.

To contrast with feature annotations, there are two differences:
* The filtering is done during analysis itself, and limits the issues generated (as opposed to a post-processing step by the user)
* Taint in taint out transforms can be used to reason about the order of events

### Syntax
In `taint.config`, one can specify `transforms` to define new transforms. Each transform is defined by following fields:
* `name`: name of the transform, this is used when defining rules, as well as writing models
* `comment`: description of the transform

```
{
  ...
  "transforms": [
    {
      "name": "MyTransform",
      "comment": "This is my transform"
    },
    ...
  ],
  ...
}
```

Then, one may use these transforms in `rules` as follows:
```
 {
  ...
  "rules": [
    {
      "name": ...,
      "code": ...,
      "sources": ["SourceA"],
      "transforms": ["MyTransform1", "MyTransform2"],
      "sinks": ["SinkB"],
      "message_format": "[{$sources}] transformed by [${transforms}] may reach [${sinks}]"
    },
    ...
  ],
  ...
}
```
Intuitively, one can think of the rule above as `SourceA -> MyTransform1 -> MyTransform2 -> SinkB`. The order is important.

Finally, in `.pysa` model files a taint transform can be specified using a `TaintInTaintOut[Transform[...]]` annotation, where the parameter is the name of the transform.
```
def my_function(arg: TaintInTaintOut[Transform[MyTransform]]): ...
```

### Semantics
```
  y = my_function(x)
```
If `x` has source taint `SourceA`, the taint of `y` is `MyTransform:SourceA`. This will correspond to matching `SourceA -> MyTransform` in a rule. Likewise, if `y` has sink taint `SinkB`, then the taint of `x` is `MyTransorm:SinkB`. This will correspond to matching `MyTransform -> SinkB` in a rule.

Note that a transform modifies the taint itself. Hence, if a flow passes through a transform, it will no longer match rules which do not contain the transform.
```
RuleX: SourceA -> SinkB
RuleY: SourceA -> MyTransform -> SinkB
Flow1: SourceA -> SinkB
Flow2: SourceA -> MyTransform -> SinkB
```
`Flow1` matches `RuleX` but not `RuleY`. `Flow2` matches `RuleY` but not `RuleX`.

Consider the scenario where we have an additional rule:
```
RuleZ: SourceC -> SinkD
```
If transform `MyTransform` is applied to taint `SourceC`, there is no possible rule it can possibly match. As an optimization, we check for this continuously in our analysis and filter out eagerly.

Also note that the existing TaintInTaintOut annotation semantics of TITO being assumed (instead of inferred) on the argument are unchanged.

## Tune the taint tree width and depth

Pysa provides many options to fine tune the taint analysis. The following
options can be provided either via the command line or in the `taint.config` file,
under the `options` section.

For instance:
```json
{
  "sources": [],
  "sinks": [],
  "features": [],
  "rules": [],
  "options": {
    "maximum_model_source_tree_width": 10,
    "maximum_model_sink_tree_width": 10,
    "maximum_model_tito_tree_width": 10
  }
}
```

When not provided, these are set to the following defaults:
```ocaml file=source/interprocedural_analyses/taint/taintConfiguration.ml start=DOCUMENTATION_CONFIGURATION_START end=DOCUMENTATION_CONFIGURATION_END

```

### Maximum model source tree width

* Command line option: `--maximum-model-source-tree-width`
* taint.config option: `maximum_model_source_tree_width`

This limits the width of the source tree in the model for a callable, i.e
the number of output paths in the return value.

For instance:
```python
def foo():
  return {"a": source(), "b": source(), "c": source()}
```

The source tree for `foo` has a width of 3. Above the provided threshold, pysa
will collapse the taint and consider the whole dictionary tainted. When that
happens, the breadcrumbs `model-broadening` and `model-source-broadening` will
be added to the flow.

### Maximum model sink tree width

* Command line option: `--maximum-model-sink-tree-width`
* taint.config option: `maximum_model_sink_tree_width`

This limits the width of the sink tree in the model for a callable, i.e
the number of input paths leading to a sink for a given parameter.

For instance:
```python
def foo(arg):
  sink(arg[1])
  sink(arg[2])
  sink(arg[3])
```

The sink tree for `foo` and parameter `arg` has a width of 3.
Above the provided threshold, pysa will collapse the taint and consider that the
whole argument leads to a sink. When that happens, the breadcrumbs
`model-broadening` and `model-sink-broadening` will be added to the flow.

### Maximum model tito tree width

* Command line option: `--maximum-model-tito-tree-width`
* taint.config option: `maximum_model_tito_tree_width`

This limits the width of the taint-in-taint-out tree in the model for a callable,
i.e the number of input paths propagated to the return value, for a given parameter.

For instance:
```python
def foo(arg):
  return '%s:%s:%s' % (arg.a, arg.b, arg.c)
```

The taint-in-taint-out tree for `foo` and parameter `arg` has a width of 3.
Above the provided threshold, pysa will collapse the taint and consider that the
taint on the whole argument is propagated to the return value. When that
happens, the breadcrumbs `model-broadening` and `model-tito-broadening` will be
added to the flow.

### Maximum tree depth after widening

* Command line option: `--maximum-tree-depth-after-widening`
* taint.config option: `maximum_tree_depth_after_widening`

This limits the depth of the source, sink and tito trees within loops, i.e the
length of source, sink and tito paths for each variables.

For instance:
```python
def foo():
  variable = MyClass()
  for x in generate():
    variable.a.b.c = source()
  return result
```

The source tree for `variable` has a depth of 3 (i.e, `a` -> `b` -> `c`).
Within a loop, pysa limits the depth to the provided threshold. For instance,
if that threshold is 1, we would consider that `variable.a` is entirely tainted.
When that happens, the breadcrumb `widen-broadening` will be added to the flow.

### Maximum return access path width

* Command line option: `--maximum-return-access-path-width`
* taint.config option: `maximum_return_access_path_width`

This limits the width of the return access path tree in the model for a callable,
i.e the number of output paths propagated to the return value, for a given parameter.

For instance:
```python
def foo(arg):
  return {'a': arg, 'b': arg, 'c': arg}
```

The return access path tree for `foo` and parameter `arg` has a width of 3.
Above the provided threshold, pysa will collapse the taint and consider that the
whole return value is tainted whenever `arg` is tainted. When that happens,
the breadcrumbs `model-broadening` and `model-tito-broadering` will be added to
the flow.

### Maximum return access path depth after widening

* Command line option: `--maximum-return-access-path-depth-after-widening`
* taint.config option: `maximum_return_access_path_depth_after_widening`

This limits the depth of the return access path tree within loops, i.e the
length of output paths propagated to the return value, for a given parameter.

For instance:
```python
def foo(arg):
  result = MyClass()
  for x in generate():
    result.a.b.c = arg
  return result
```

The return access path tree for `foo` and parameter `arg` has a depth  of 3
(i.e, `a` -> `b` -> `c`). Within a loop, pysa limits the depth to the provided
threshold. For instance, if that threshold is 2, we would cut the output path
to just `a.b`. When that happens, the breadcrumb `model-broadening` and
`model-tito-broadening` will be added to the flow.

### Maximum tito collapse depth

* Command line option: `--maximum-tito-collapse-depth`
* taint.config option: `maximum_tito_collapse_depth`

This limits the depth of the taint tree after applying taint-in-taint-out,
i.e the length of paths for taint propagated from a parameter to the return
value.

For instance:
```python
def identity(arg): return arg

def foo():
  input = {'a': {'b': {'c': source()}}}
  output = identity(input)
```

The taint tree for `input` has a depth of 3 (i.e, `a` -> `b` -> `c`).
When the taint is propagated to the return value of `identity`, we limit
the resulting taint tree to the given depth. For instance, if that threshold
is 1, we would consider that `output['a']` is tainted.

This is also applied for sinks in the backward analysis:
```python
def foo(arg):
  output = identity(arg)
  sink(output['a']['b']['c'])
```
With a threshold of 1, we would consider that `output['a']` leads to a sink.

### Maximum tito positions

* Command line option: `--maximum-tito-positions`
* taint.config option: `maximum_tito_positions`

This limits the number of positions to keep track of when propagating taint.

When taint is propagated through a function and returned (i.e, taint-in-taint-out),
pysa will keep track of the position of the argument, and display it in the trace.

For instance:
```python
def foo():
  x = source()
  y = tito(x)
           ^
  z = {"a": y}
            ^
  sink(z)
```

In this example, we have 2 tito positions. Above the provided threshold,
pysa simply discards all positions. Note that the taint is still propagated.