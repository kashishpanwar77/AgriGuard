document.addEventListener("DOMContentLoaded", function () {

    const form = document.querySelector("form");
    const lossInput = document.querySelector('[name="loss_percentage"]');
    const quantityInput = document.querySelector('[name="quantity"]');
    const riskPreview = document.getElementById("riskPreview");

    if (!form) {
        return;
    }

    lossInput.addEventListener("input", function () {

        const loss = parseFloat(lossInput.value);

        if (isNaN(loss)) {
            riskPreview.textContent = "Risk level will appear here";
            return;
        }

        if (loss < 3) {
            riskPreview.textContent = "🟢 Low Risk";
        } else if (loss < 6) {
            riskPreview.textContent = "🟡 Medium Risk";
        } else {
            riskPreview.textContent = "🔴 High Risk";
        }
    });


    form.addEventListener("submit", function (event) {

        const quantity = parseFloat(quantityInput.value);
        const loss = parseFloat(lossInput.value);

        if (quantity <= 0) {
            event.preventDefault();
            alert("Quantity must be greater than 0.");
            return;
        }

        if (loss < 0 || loss > 100) {
            event.preventDefault();
            alert("Loss percentage must be between 0 and 100.");
            return;
        }
    });

});