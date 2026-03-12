(function () {
  class SlotSocket {
    constructor({ onMessage, onFallbackPoll }) {
      this.onMessage = onMessage;
      this.onFallbackPoll = onFallbackPoll;
      this.retryCount = 0;
      this.maxRetry = 6;
      this.poller = null;
      this.socket = null;
    }

    connect() {
      const protocol = window.location.protocol === "https:" ? "wss" : "ws";
      const wsUrl = `${protocol}://${window.location.host}/api/ws/slots`;

      this.socket = new WebSocket(wsUrl);

      this.socket.onopen = () => {
        this.retryCount = 0;
        this.stopPolling();
      };

      this.socket.onmessage = (event) => {
        const payload = JSON.parse(event.data);
        if (payload.type === "heartbeat") return;
        this.onMessage?.(payload);
      };

      this.socket.onclose = () => {
        this.reconnect();
      };

      this.socket.onerror = () => {
        this.socket?.close();
      };
    }

    reconnect() {
      if (this.retryCount >= this.maxRetry) {
        this.startPolling();
        return;
      }
      const backoff = Math.min(16000, 1000 * 2 ** this.retryCount);
      this.retryCount += 1;
      setTimeout(() => this.connect(), backoff);
    }

    startPolling() {
      if (this.poller) return;
      this.poller = setInterval(() => {
        this.onFallbackPoll?.();
      }, 10000);
    }

    stopPolling() {
      if (this.poller) {
        clearInterval(this.poller);
        this.poller = null;
      }
    }
  }

  window.ParkVisionSlotSocket = SlotSocket;
})();
