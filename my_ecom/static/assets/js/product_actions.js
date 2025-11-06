function getCookie(name) {
	let cookieValue = null;
	if (document.cookie && document.cookie !== "") {
		const cookies = document.cookie.split(";");
		for (let i = 0; i < cookies.length; i++) {
			const cookie = cookies[i].trim();
			if (cookie.startsWith(name + "=")) {
				cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
				break;
			}
		}
	}
	return cookieValue;
}

function handleProductAction(productId, action) {
	const csrfToken = getCookie("csrftoken");
	const formData = new FormData();
	formData.append("product_id", productId);
	formData.append("action", action);

	fetch("/handle-product-action/", {
		method: "POST",
		headers: {
			"X-CSRFToken": csrfToken,
			"X-Requested-With": "XMLHttpRequest",
		},
		body: formData,
	})
	.then(response => response.json())
	.then(data => {
		if (data.success) {
			// ✅ Success message
			showFloatingMessage(data.message || "Success!", "success");

			// ✅ Wishlist or Cart page open in new tab
			if (action === "cart") {
				window.open("/shopping-cart/", "_blank");
			} else if (action === "wishlist") {
				window.open("/wishlist/", "_blank");
			}
		} else {
			showFloatingMessage(data.message || "Something went wrong!", "error");
		}
	})
	.catch(error => {
		console.error("Error:", error);
		showFloatingMessage("Error processing your request.", "error");
	});
}

// ✅ Floating toast message
function showFloatingMessage(message, type) {
	const msgBox = document.createElement("div");
	msgBox.textContent = message;
	msgBox.style.position = "fixed";
	msgBox.style.top = "20px";
	msgBox.style.right = "20px";
	msgBox.style.background = type === "success" ? "#28a745" : "#dc3545";
	msgBox.style.color = "#fff";
	msgBox.style.padding = "10px 20px";
	msgBox.style.borderRadius = "6px";
	msgBox.style.boxShadow = "0 2px 8px rgba(0,0,0,0.2)";
	msgBox.style.zIndex = "9999";
	msgBox.style.transition = "opacity 0.3s ease";
	document.body.appendChild(msgBox);

	setTimeout(() => {
		msgBox.style.opacity = "0";
		setTimeout(() => msgBox.remove(), 500);
	}, 1500);
}


document.addEventListener('DOMContentLoaded', function () {
    const quantityInputs = document.querySelectorAll('.cart-action input[type="number"]');

    quantityInputs.forEach(input => {
        input.addEventListener('change', function () {
            const itemId = this.dataset.itemId;
            let quantity = parseInt(this.value);
            if (quantity < 1) quantity = 1;

            const formData = new FormData();
            formData.append('item_id', itemId);
            formData.append('quantity', quantity);

            fetch("{% url 'update_cart_quantity' %}", {
                method: 'POST',
                headers: {
                    'X-CSRFToken': '{{ csrf_token }}',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: formData
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    // Update item subtotal
                    const itemRow = input.closest('.row');
                    const itemTotalEl = itemRow.querySelector('h5');
                    itemTotalEl.textContent = `ItemTotal: $${data.item_total}`;

                    // Update cart subtotal (you can target your subtotal element)
                    const cartSubtotalEl = document.querySelector('#cart-subtotal'); // add id="cart-subtotal" to your subtotal element
                    if(cartSubtotalEl){
                        cartSubtotalEl.textContent = `$${data.cart_subtotal}`;
                    }

                    // Update cart total items badge
                    document.querySelectorAll('.alert-count').forEach(el => {
                        el.textContent = data.cart_total_items;
                    });
                }
            });
        });
    });
});