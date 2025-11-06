document.addEventListener("DOMContentLoaded", function() {
    const priceField = document.querySelector("#id_price");
    const discountField = document.querySelector("#id_discount_price");
    const originalField = document.querySelector("#id_orginal_price");

    // ✅ Create a small live % label after discount field
    const percentLabel = document.createElement("small");
    percentLabel.style.marginLeft = "10px";
    percentLabel.style.color = "#007bff";
    percentLabel.style.fontWeight = "bold";
    discountField.parentNode.appendChild(percentLabel);

    function updatePercentLabel() {
        const price = parseFloat(priceField.value) || 0;
        const original = parseFloat(originalField.value) || 0;

        if (price > 0 && original > 0) {
            const percent = ((price - original) / price * 100).toFixed(2);
            percentLabel.textContent = `(${percent}% OFF)`;
        } else {
            percentLabel.textContent = "";
        }
    }

    function calculateFields(changedField) {
        const price = parseFloat(priceField.value) || 0;
        const discountPercent = parseFloat(discountField.value) || 0;
        const original = parseFloat(originalField.value) || 0;

        if (!price) return;

        // Case 1: price + discount % → calculate original price
        if (changedField === 'discount' && price && discountPercent) {
            const discountAmount = (price * discountPercent) / 100;
            originalField.value = (price - discountAmount).toFixed(2);
        }

        // Case 2: price + original price → calculate discount %
        else if (changedField === 'original' && price && original) {
            const percent = ((price - original) / price) * 100;
            discountField.value = percent.toFixed(2);
        }

        // Case 3: price changed → recalculate based on whichever exists
        else if (changedField === 'price') {
            if (discountPercent) {
                const discountAmount = (price * discountPercent) / 100;
                originalField.value = (price - discountAmount).toFixed(2);
            } else if (original) {
                const percent = ((price - original) / price) * 100;
                discountField.value = percent.toFixed(2);
            }
        }

        updatePercentLabel();
    }

    priceField.addEventListener("input", function() {
        calculateFields('price');
    });
    discountField.addEventListener("input", function() {
        calculateFields('discount');
    });
    originalField.addEventListener("input", function() {
        calculateFields('original');
    });
});
