try {
    var py_callback = arguments[arguments.length - 1];
    const a = await window.grecaptcha.enterprise.execute("6LfP64kpAAAAAP_Jl8kdL0-09UKzowM87iddJqXA", {
        action: "LOGIN"
    });
    py_callback(a)
} catch (a) {
    py_callback("")
}