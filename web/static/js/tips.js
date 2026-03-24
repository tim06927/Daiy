/**
 * Loading tips — animated display during wait times
 *
 * Tips are fetched in parallel (fastest model) and shown one-by-one
 * in a looping animation while the main request is pending.
 */

const TipsManager = {
  tips: [],
  currentIndex: 0,
  intervalId: null,
  isRunning: false,

  /** Interval between tip transitions (ms) */
  INTERVAL: 4000,

  /**
   * Start displaying tips in the loading area.
   * @param {string[]} tips - Array of tip strings from the API
   */
  start(tips) {
    if (!tips || tips.length === 0) return;

    this.tips = tips;
    this.currentIndex = 0;
    this.isRunning = true;

    const container = document.getElementById('tips-container');
    if (!container) return;

    container.classList.add('active');
    this._showTip(0);

    // Cycle through tips
    this.intervalId = setInterval(() => {
      this.currentIndex = (this.currentIndex + 1) % this.tips.length;
      this._showTip(this.currentIndex);
    }, this.INTERVAL);
  },

  /**
   * Stop the tips animation and clean up.
   */
  stop() {
    this.isRunning = false;
    if (this.intervalId) {
      clearInterval(this.intervalId);
      this.intervalId = null;
    }
    const container = document.getElementById('tips-container');
    if (container) {
      container.classList.remove('active');
    }
    this.tips = [];
    this.currentIndex = 0;
  },

  /**
   * Render a single tip with a fade transition.
   * @param {number} index
   */
  _showTip(index) {
    const tipText = document.getElementById('tip-text');
    const tipCounter = document.getElementById('tip-counter');
    if (!tipText) return;

    // Fade out
    tipText.classList.remove('visible');

    setTimeout(() => {
      tipText.textContent = this.tips[index];
      if (tipCounter) {
        tipCounter.textContent = `${index + 1} / ${this.tips.length}`;
      }
      // Fade in
      tipText.classList.add('visible');
    }, 300); // matches CSS transition duration
  }
};
