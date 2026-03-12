(function () {
  const app = document.getElementById("parking-dashboard");
  if (!app) return;

  const state = {
    zone: "A",
    floor: "",
    slots: [],
    selectedSlot: null,
    vehicles: [],
  };

  const elements = {
    grid: document.getElementById("slot-grid"),
    zoneTabs: document.querySelectorAll("[data-zone-tab]"),
    floorSelect: document.getElementById("floor-filter"),
    modal: document.getElementById("booking-modal"),
    modalClose: document.getElementById("booking-modal-close"),
    bookingForm: document.getElementById("booking-form"),
    slotMeta: document.getElementById("booking-slot-meta"),
    calcTotal: document.getElementById("booking-total"),
    calcBreakdown: document.getElementById("booking-breakdown"),
    totalSlots: document.getElementById("kpi-total-slots"),
    availableSlots: document.getElementById("kpi-available-slots"),
    occupiedSlots: document.getElementById("kpi-occupied-slots"),
    myActiveBookings: document.getElementById("kpi-my-active-bookings"),
    vehicleSelect: document.getElementById("booking-vehicle-id"),
  };

  function updateCounts(counts) {
    if (!counts) return;
    elements.totalSlots.textContent = counts.total;
    elements.availableSlots.textContent = counts.available;
    elements.occupiedSlots.textContent = counts.occupied;
  }

  function myActiveCount() {
    return state.slots.filter((slot) => slot.booked_by === window.PARK_VISION_USER?.id && slot.status === "occupied").length;
  }

  function slotTypeBadge(type) {
    if (type === "ev") return "EV ⚡";
    if (type === "handicapped") return "♿ Accessible";
    return "Standard";
  }

  function statusBadge(status) {
    if (status === "available") return "Available";
    if (status === "reserved") return "Reserved";
    return "Occupied";
  }

  function renderSlots() {
    const html = state.slots
      .map((slot) => {
        const mine = slot.booked_by === window.PARK_VISION_USER?.id;
        return `
          <article class="slot-card ${slot.status} ${mine ? "mine" : ""}" data-slot-id="${slot.id}" data-testid="slot-card-${slot.slot_code}">
            <div class="slot-top">
              <strong data-testid="slot-code-${slot.slot_code}">${slot.slot_code}</strong>
              <span class="status-dot ${slot.status}" data-testid="slot-status-dot-${slot.slot_code}"></span>
            </div>
            <small class="text-muted" data-testid="slot-type-${slot.slot_code}">${slotTypeBadge(slot.slot_type)}</small>
            <div class="badge ${slot.status}" data-testid="slot-status-${slot.slot_code}">${statusBadge(slot.status)}</div>
            ${mine ? '<div class="badge" style="border-color:rgba(0,212,255,.5);">YOUR SPOT</div>' : ""}
          </article>
        `;
      })
      .join("");

    elements.grid.innerHTML = html;
    elements.myActiveBookings.textContent = myActiveCount();

    elements.grid.querySelectorAll("[data-slot-id]").forEach((card) => {
      card.addEventListener("click", () => {
        const id = Number(card.getAttribute("data-slot-id"));
        const slot = state.slots.find((s) => s.id === id);
        if (!slot || slot.status !== "available") return;
        openBookingModal(slot);
      });
    });
  }

  async function fetchSlots() {
    const params = new URLSearchParams({ zone: state.zone });
    if (state.floor) params.append("floor", state.floor);
    const data = await window.ParkVision.fetchJSON(`/api/slots?${params.toString()}`);
    state.slots = data.slots;
    updateCounts(data.counts);
    renderSlots();
  }

  function populateVehicleOptions() {
    elements.vehicleSelect.innerHTML = state.vehicles
      .map(
        (vehicle) =>
          `<option value="${vehicle.id}" ${vehicle.is_primary ? "selected" : ""}>${vehicle.number_plate} (${vehicle.vehicle_type.toUpperCase()})</option>`,
      )
      .join("");
  }

  function openBookingModal(slot) {
    state.selectedSlot = slot;
    elements.slotMeta.textContent = `${slot.slot_code} • Zone ${slot.zone} • ${slotTypeBadge(slot.slot_type)}`;
    elements.modal.classList.add("open");
    elements.modal.setAttribute("aria-hidden", "false");
    calculateBookingTotal();
  }

  function closeBookingModal() {
    elements.modal.classList.remove("open");
    elements.modal.setAttribute("aria-hidden", "true");
    state.selectedSlot = null;
  }

  function calculateBookingTotal() {
    const checkIn = new Date(document.getElementById("booking-check-in").value);
    const checkOut = new Date(document.getElementById("booking-check-out").value);
    if (Number.isNaN(checkIn.getTime()) || Number.isNaN(checkOut.getTime())) {
      elements.calcTotal.textContent = "₹0.00";
      elements.calcBreakdown.textContent = "Select a valid time range";
      return;
    }

    const diffHours = (checkOut - checkIn) / (1000 * 60 * 60);
    if (diffHours <= 0) return;
    const amount = diffHours * 20;
    const tax = amount * 0.18;
    const total = amount + tax;
    elements.calcTotal.textContent = window.ParkVision.formatRupee(total);
    elements.calcBreakdown.textContent = `${diffHours.toFixed(2)}h × ₹20 + 18% GST`;
  }

  async function createBooking(event) {
    event.preventDefault();
    if (!state.selectedSlot) return;

    const button = document.getElementById("booking-submit-button");
    button.disabled = true;
    button.innerHTML = '<span class="loading-spinner"></span> Reserving...';

    try {
      const payload = {
        slot_id: state.selectedSlot.id,
        vehicle_id: Number(document.getElementById("booking-vehicle-id").value),
        check_in: document.getElementById("booking-check-in").value,
        check_out: document.getElementById("booking-check-out").value,
      };

      const data = await window.ParkVision.fetchJSON("/api/bookings", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      window.ParkVision.showToast("Booking created. Redirecting to payment...");
      window.location.href = data.redirect_url;
    } catch (error) {
      window.ParkVision.showToast(error.message, "error");
    } finally {
      button.disabled = false;
      button.textContent = "Book & Proceed to Payment";
    }
  }

  function setupEvents() {
    elements.zoneTabs.forEach((tab) => {
      tab.addEventListener("click", async () => {
        elements.zoneTabs.forEach((btn) => btn.classList.remove("active"));
        tab.classList.add("active");
        state.zone = tab.getAttribute("data-zone-tab");
        await fetchSlots();
      });
    });

    elements.floorSelect.addEventListener("change", async () => {
      state.floor = elements.floorSelect.value;
      await fetchSlots();
    });

    elements.modalClose.addEventListener("click", closeBookingModal);
    elements.modal.addEventListener("click", (event) => {
      if (event.target === elements.modal) closeBookingModal();
    });

    document.getElementById("booking-check-in").addEventListener("change", calculateBookingTotal);
    document.getElementById("booking-check-out").addEventListener("change", calculateBookingTotal);
    elements.bookingForm.addEventListener("submit", createBooking);
  }

  function initSocket() {
    const socket = new window.ParkVisionSlotSocket({
      onMessage(payload) {
        if (payload.type === "snapshot") {
          state.slots = payload.slots;
          updateCounts(payload.counts);
          renderSlots();
          return;
        }
        if (payload.type === "slot_update" && payload.slot) {
          const index = state.slots.findIndex((slot) => slot.id === payload.slot.id);
          if (index >= 0) state.slots[index] = { ...state.slots[index], ...payload.slot };
          updateCounts(payload.counts);
          renderSlots();
        }
      },
      onFallbackPoll: fetchSlots,
    });
    socket.connect();
  }

  async function init() {
    state.vehicles = window.DASHBOARD_VEHICLES || [];
    populateVehicleOptions();
    setupEvents();
    await fetchSlots();
    initSocket();
  }

  init();
})();
