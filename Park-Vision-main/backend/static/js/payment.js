(function () {
  const page = document.getElementById("payment-page");
  if (!page) return;

  const state = {
    method: "card",
    booking: window.PAYMENT_BOOKING,
    paymentId: null,
    discountedTotal: null,
  };

  const tabs = document.querySelectorAll("[data-payment-tab]");
  const panels = document.querySelectorAll("[data-payment-panel]");
  const cardNumberInput = document.getElementById("card-number");
  const cardTypeEl = document.getElementById("card-type-detected");
  const preview = document.getElementById("card-preview");
  const totalEl = document.getElementById("payment-total-value");

  function setMethod(method) {
    state.method = method;
    tabs.forEach((tab) => tab.classList.toggle("active", tab.getAttribute("data-payment-tab") === method));
    panels.forEach((panel) => panel.classList.toggle("active", panel.getAttribute("data-payment-panel") === method));
  }

  function detectCardType(number) {
    if (/^4/.test(number)) return "Visa";
    if (/^5[1-5]/.test(number)) return "Mastercard";
    if (/^6/.test(number)) return "Rupay";
    return "Card";
  }

  function formatCardNumber(value) {
    return value
      .replace(/\D/g, "")
      .slice(0, 16)
      .replace(/(.{4})/g, "$1 ")
      .trim();
  }

  async function applyPromo() {
    const code = document.getElementById("promo-code").value;
    try {
      const data = await window.ParkVision.fetchJSON("/api/payments/promo", {
        method: "POST",
        body: JSON.stringify({ code, total: state.booking.total }),
      });
      if (!data.valid) {
        window.ParkVision.showToast(data.message, "error");
        return;
      }
      state.discountedTotal = data.new_total;
      totalEl.textContent = window.ParkVision.formatRupee(state.discountedTotal);
      window.ParkVision.showToast("Promo applied: 20% off");
    } catch (error) {
      window.ParkVision.showToast(error.message, "error");
    }
  }

  async function payNow() {
    const button = document.getElementById("pay-now-button");
    button.disabled = true;
    button.innerHTML = '<span class="loading-spinner"></span> Processing...';

    try {
      const initiate = await window.ParkVision.fetchJSON("/api/payments/initiate", {
        method: "POST",
        body: JSON.stringify({
          booking_id: state.booking.id,
          payment_method: state.method,
          payment_details: {},
        }),
      });
      state.paymentId = initiate.payment_id;

      const verify = await window.ParkVision.fetchJSON("/api/payments/verify", {
        method: "POST",
        body: JSON.stringify({ payment_id: state.paymentId }),
      });

      if (!verify.success) {
        window.ParkVision.showToast(verify.message || "Payment failed", "error");
        return;
      }

      window.ParkVision.showToast("Payment successful!");
      window.location.href = verify.redirect_url;
    } catch (error) {
      window.ParkVision.showToast(error.message, "error");
    } finally {
      button.disabled = false;
      button.textContent = "Pay Now";
    }
  }

  function setupCardInteractions() {
    if (!cardNumberInput) return;
    cardNumberInput.addEventListener("input", () => {
      cardNumberInput.value = formatCardNumber(cardNumberInput.value);
      const type = detectCardType(cardNumberInput.value.replace(/\s/g, ""));
      cardTypeEl.textContent = type;
    });

    const cvv = document.getElementById("card-cvv");
    cvv.addEventListener("focus", () => preview.classList.add("flipped"));
    cvv.addEventListener("blur", () => preview.classList.remove("flipped"));
  }

  function setup() {
    tabs.forEach((tab) => {
      tab.addEventListener("click", () => setMethod(tab.getAttribute("data-payment-tab")));
    });

    setupCardInteractions();
    document.getElementById("promo-apply-button").addEventListener("click", applyPromo);
    document.getElementById("pay-now-button").addEventListener("click", payNow);

    totalEl.textContent = window.ParkVision.formatRupee(state.booking.total);
  }

  setup();
})();
