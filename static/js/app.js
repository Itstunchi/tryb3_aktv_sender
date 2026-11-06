/**
 * TermSender Pro - JavaScript Application
 * Modern email campaign management interface
 */

class TermSenderApp {
  constructor() {
    this.currentSection = "dashboard";
    this.smtpServers = []; // Changed from single config to array
    this.rotationSettings = {
      mode: "email_count",
      emailsPerRotation: 10,
      secondsPerRotation: 30,
      delayBetweenEmails: 1,
      enableFailover: true,
      maxRetries: 3,
    };
    this.emailContent = null;
    this.recipients = [];
    this.attachments = [];
    this.isReady = false;
    this.isLoading = false;
    this.isPaused = false; // For pause/resume streaming
    this.editingSmtpIndex = -1; // For editing existing SMTP servers
    this.editorRange = null;
    this.inlineImageUrls = new Map();

    this.init();
  }

  init() {
    console.log("Initializing TermSender Pro...");

    // Make sure loading is hidden initially
    this.hideLoading();

    this.setupEventListeners();
    this.applyTheme(localStorage.getItem("ts_theme") || "dark");

    // Load saved data from server
    this.loadSavedData();

    // Only show compliance modal if not already accepted
    const complianceAccepted = sessionStorage.getItem("complianceAccepted");
    if (!complianceAccepted) {
      // Small delay to ensure DOM is ready
      setTimeout(() => {
        this.showComplianceModal();
      }, 100);
    }

    this.updateDashboard();
    console.log("TermSender Pro initialized successfully");
  }

  setupEventListeners() {
    // Navigation
    document.querySelectorAll(".nav-item").forEach((item) => {
      item.addEventListener("click", (e) => {
        const section = e.currentTarget.dataset.section;
        this.navigateToSection(section);
      });
    });

    // Dashboard cards navigation
    document.querySelectorAll(".dashboard-card").forEach((card) => {
      card.addEventListener("click", (e) => {
        const cardIcon = e.currentTarget.querySelector(".card-icon");
        let section = "dashboard";

        if (cardIcon.classList.contains("smtp-icon")) section = "smtp";
        else if (cardIcon.classList.contains("recipients-icon"))
          section = "recipients";
        else if (cardIcon.classList.contains("compose-icon"))
          section = "compose";
        else if (cardIcon.classList.contains("send-icon")) section = "send";

        this.navigateToSection(section);
      });
    });

    // Filter chips event delegation
    document.addEventListener("click", (e) => {
      if (e.target.closest(".filter-chip")) {
        const chip = e.target.closest(".filter-chip");
        document
          .querySelectorAll(".filter-chip")
          .forEach((c) => c.classList.remove("active"));
        chip.classList.add("active");

        // Re-render the table with the current filter
        const filter = chip.dataset.filter;
        this.applyTableFilter(filter);
      }
    });

    // Pause/Resume streaming button
    document.addEventListener("click", (e) => {
      if (e.target.closest("#pauseResumeBtn")) {
        this.togglePauseResume();
      }
    });

    // SMTP Form
    this.setupSMTPEventListeners();

    // Recipients
    this.setupRecipientsEventListeners();

    // Compose
    this.setupComposeEventListeners();

    // Attachments
    this.setupAttachmentsEventListeners();

    // Send
    this.setupSendEventListeners();

    // Compliance Modal
    this.setupComplianceEventListeners();

    // Settings modal wiring
    const settingsBtn = document.getElementById("settingsBtn");
    const settingsModal = document.getElementById("settingsModal");
    const closeSettingsModal = document.getElementById("closeSettingsModal");
    const saveSettingsBtn = document.getElementById("saveSettingsBtn");
    const resetSettingsBtn = document.getElementById("resetSettingsBtn");

    if (settingsBtn && settingsModal) {
      settingsBtn.addEventListener("click", () => {
        settingsModal.style.display = "flex";
      });
    }
    if (closeSettingsModal && settingsModal) {
      closeSettingsModal.addEventListener("click", () => {
        settingsModal.style.display = "none";
      });
    }
    if (saveSettingsBtn && settingsModal) {
      saveSettingsBtn.addEventListener("click", () => {
        // Persist simple preferences in localStorage
        const theme = document.getElementById("appTheme")?.value || "dark";
        const toasts =
          document.getElementById("enableToasts")?.checked !== false;
        localStorage.setItem("ts_theme", theme);
        localStorage.setItem("ts_toasts", String(toasts));
        this.applyTheme(theme);
        this.showNotification("Settings saved", "success");
        settingsModal.style.display = "none";
      });
    }
    if (resetSettingsBtn) {
      resetSettingsBtn.addEventListener("click", () => {
        localStorage.removeItem("ts_theme");
        localStorage.removeItem("ts_toasts");
        const themeSelect = document.getElementById("appTheme");
        const toastChk = document.getElementById("enableToasts");
        if (themeSelect) themeSelect.value = "dark";
        this.applyTheme("dark");
        if (toastChk) toastChk.checked = true;
        this.showNotification("Settings reset", "info");
      });
    }
  }

  applyTheme(theme) {
    const selected = theme === "light" ? "light" : "dark";
    document.documentElement.dataset.theme = selected;
    const select = document.getElementById("appTheme");
    if (select) select.value = selected;
  }

  setupSMTPEventListeners() {
    // Add SMTP Server buttons
    const addSmtpBtn = document.getElementById("addSmtpBtn");
    const addFirstSmtpBtn = document.getElementById("addFirstSmtpBtn");

    if (addSmtpBtn) {
      addSmtpBtn.addEventListener("click", () => this.showSMTPModal());
    }
    if (addFirstSmtpBtn) {
      addFirstSmtpBtn.addEventListener("click", () => this.showSMTPModal());
    }

    // SMTP Modal
    const smtpForm = document.getElementById("smtpForm");
    const testBtn = document.getElementById("testSmtpBtn");
    const closeModalBtn = document.getElementById("closeSmtpModal");

    if (smtpForm) {
      smtpForm.addEventListener("submit", (e) => {
        e.preventDefault();
        this.saveSMTPServer();
      });
    }

    if (testBtn) {
      testBtn.addEventListener("click", () => {
        this.testSMTPConnection();
      });
    }

    if (closeModalBtn) {
      closeModalBtn.addEventListener("click", () => {
        this.hideSMTPModal();
      });
    }

    // Rotation Settings
    const rotationMode = document.getElementById("rotationMode");
    const saveRotationBtn = document.getElementById("saveRotationBtn");
    const testAllSmtpBtn = document.getElementById("testAllSmtpBtn");

    if (rotationMode) {
      rotationMode.addEventListener("change", (e) => {
        this.toggleRotationSettings(e.target.value);
      });
    }

    if (saveRotationBtn) {
      saveRotationBtn.addEventListener("click", () => {
        this.saveRotationSettings();
      });
    }

    if (testAllSmtpBtn) {
      testAllSmtpBtn.addEventListener("click", () => {
        this.testAllSMTPServers();
      });
    }

    // Auto-fill sender email when username changes
    const smtpUsername = document.getElementById("smtpUsername");
    const senderEmail = document.getElementById("senderEmail");
    const encTLS = document.getElementById("encryptionTLS");
    const encSSL = document.getElementById("encryptionSSL");

    if (smtpUsername && senderEmail) {
      smtpUsername.addEventListener("input", (e) => {
        if (!senderEmail.value) {
          senderEmail.value = e.target.value;
        }
      });
    }
    // Encryption toggles update recommended port
    const portInput = document.getElementById("smtpPort");
    if (encTLS && portInput) {
      encTLS.addEventListener("change", () => {
        if (encTLS.checked) portInput.value = 587;
      });
    }
    if (encSSL && portInput) {
      encSSL.addEventListener("change", () => {
        if (encSSL.checked) portInput.value = 465;
      });
    }
  }

  setupRecipientsEventListeners() {
    // CSV Upload
    const csvDropZone = document.getElementById("csvDropZone");
    const csvFileInput = document.getElementById("csvFileInput");
    const csvBrowseBtn = document.getElementById("csvBrowseBtn");

    if (csvDropZone && csvFileInput && csvBrowseBtn) {
      // File drag and drop
      csvDropZone.addEventListener("dragover", (e) => {
        e.preventDefault();
        csvDropZone.classList.add("dragover");
      });

      csvDropZone.addEventListener("dragleave", () => {
        csvDropZone.classList.remove("dragover");
      });

      csvDropZone.addEventListener("drop", (e) => {
        e.preventDefault();
        csvDropZone.classList.remove("dragover");
        const files = e.dataTransfer.files;
        if (files.length > 0) {
          this.handleCSVUpload(files[0]);
        }
      });

      csvBrowseBtn.addEventListener("click", () => csvFileInput.click());
      csvFileInput.addEventListener("change", (e) => {
        if (e.target.files.length > 0) {
          this.handleCSVUpload(e.target.files[0]);
        }
      });
    }

    // Manual entry
    const addManualBtn = document.getElementById("addManualBtn");
    if (addManualBtn) {
      addManualBtn.addEventListener("click", () => {
        this.addManualEmails();
      });
    }

    // Recipients actions
    const validateEmailsBtn = document.getElementById("validateEmailsBtn");
    const clearRecipientsBtn = document.getElementById("clearRecipientsBtn");

    if (validateEmailsBtn) {
      validateEmailsBtn.addEventListener("click", () => {
        this.validateAllEmails();
      });
    }

    if (clearRecipientsBtn) {
      clearRecipientsBtn.addEventListener("click", () => {
        this.clearAllRecipients();
      });
    }
  }

  setupComposeEventListeners() {
    const composeForm = document.getElementById("composeForm");
    const formatTabs = document.querySelectorAll(".format-tab");
    const emailSubject = document.getElementById("emailSubject");
    const emailBody = document.getElementById("emailBody");
    const emailBodyPlain = document.getElementById("emailBodyPlain");
    const inlineImageInput = document.getElementById("inlineImageInput");

    if (composeForm) {
      composeForm.addEventListener("submit", (e) => {
        e.preventDefault();
        this.saveEmailContent();
      });
    }

    // Format tabs
    formatTabs.forEach((tab) => {
      tab.addEventListener("click", (e) => {
        e.preventDefault();
        this.switchEmailFormat(e.currentTarget.dataset.format);
      });
    });

    // Live preview
    if (emailSubject) {
      emailSubject.addEventListener("input", () => this.updatePreview());
    }
    if (emailBody) {
      emailBody.addEventListener("input", () => this.updatePreview());
      const rememberRange = () => this.saveEditorSelection();
      emailBody.addEventListener("keyup", rememberRange);
      emailBody.addEventListener("mouseup", rememberRange);
    }
    if (emailBodyPlain) {
      emailBodyPlain.addEventListener("input", () => this.updatePreview());
    }

    // Rich text editor toolbar
    document.querySelectorAll(".toolbar-btn").forEach((btn) => {
      btn.addEventListener("mousedown", (e) => e.preventDefault());
      btn.addEventListener("click", (e) => {
        e.preventDefault();
        this.executeEditorCommand(e.currentTarget.dataset.action);
      });
    });

    if (inlineImageInput) {
      inlineImageInput.addEventListener("change", async (e) => {
        const file = e.target.files?.[0];
        e.target.value = "";
        if (file) await this.insertInlineImage(file);
      });
    }
  }

  setupAttachmentsEventListeners() {
    const attachmentDropZone = document.getElementById("attachmentDropZone");
    const attachmentFileInput = document.getElementById("attachmentFileInput");
    const attachmentBrowseBtn = document.getElementById("attachmentBrowseBtn");
    document.getElementById("closeAttachmentPreview")?.addEventListener("click", () => this.closeAttachmentPreview());
    document.getElementById("attachmentPreviewModal")?.addEventListener("click", (e) => {
      if (e.target.id === "attachmentPreviewModal") this.closeAttachmentPreview();
    });

    if (attachmentDropZone && attachmentFileInput && attachmentBrowseBtn) {
      // File drag and drop
      attachmentDropZone.addEventListener("dragover", (e) => {
        e.preventDefault();
        attachmentDropZone.classList.add("dragover");
      });

      attachmentDropZone.addEventListener("dragleave", () => {
        attachmentDropZone.classList.remove("dragover");
      });

      attachmentDropZone.addEventListener("drop", (e) => {
        e.preventDefault();
        attachmentDropZone.classList.remove("dragover");
        const files = e.dataTransfer.files;
        for (let file of files) {
          this.handleAttachmentUpload(file);
        }
      });

      attachmentBrowseBtn.addEventListener("click", () =>
        attachmentFileInput.click()
      );
      attachmentFileInput.addEventListener("change", (e) => {
        for (let file of e.target.files) {
          this.handleAttachmentUpload(file);
        }
      });
    }
  }

  saveEditorSelection() {
    const editor = document.getElementById("emailBody");
    const selection = window.getSelection();
    if (!editor || !selection?.rangeCount) return;
    const range = selection.getRangeAt(0);
    if (editor.contains(range.commonAncestorContainer)) this.editorRange = range.cloneRange();
  }

  restoreEditorSelection() {
    const editor = document.getElementById("emailBody");
    if (!editor || !this.editorRange) return false;
    editor.focus();
    const selection = window.getSelection();
    selection.removeAllRanges();
    selection.addRange(this.editorRange);
    return true;
  }

  setupSendEventListeners() {
    const launchBtn = document.getElementById("launchBtn");
    if (launchBtn) {
      launchBtn.addEventListener("click", () => {
        this.launchCampaign();
      });
    }
    // Live actions
    const clearBtn = document.getElementById("clearLiveBtn");
    if (clearBtn) {
      clearBtn.addEventListener("click", () => {
        const liveLog = document.getElementById("liveLog");
        if (liveLog) {
          liveLog.innerHTML = `
            <div class="log-entry initial">
              <span class="log-time">${new Date().toLocaleTimeString()}</span>
              <span class="log-message">Live activity cleared</span>
            </div>`;
        }
        const tbody = document.getElementById("liveActivityTable");
        if (tbody) tbody.innerHTML = "";
      });
    }

    const exportBtn = document.getElementById("exportLiveCsvBtn");
    if (exportBtn) {
      exportBtn.addEventListener("click", () => {
        const tbody = document.getElementById("liveActivityTable");
        if (!tbody) return;
        const rows = Array.from(tbody.querySelectorAll("tr"));
        let csv = ["Time,Status,Email,Subject,SMTP,Details"]; // header
        for (const tr of rows.reverse()) {
          // export in chronological order
          const cells = Array.from(tr.querySelectorAll("td")).map((td, idx) => {
            // Strip icons for status
            if (idx === 1) {
              const ok = td.querySelector(".fa-check-circle")
                ? "sent"
                : td.querySelector(".fa-times-circle")
                ? "failed"
                : "";
              return ok;
            }
            return (td.textContent || "")
              .replace(/\n/g, " ")
              .replace(/,/g, " ")
              .trim();
          });
          csv.push(cells.join(","));
        }
        const blob = new Blob([csv.join("\n")], {
          type: "text/csv;charset=utf-8;",
        });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `live_activity_${new Date()
          .toISOString()
          .replace(/[:.]/g, "-")}.csv`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      });
    }
  }

  setupComplianceEventListeners() {
    const acceptBtn = document.getElementById("acceptCompliance");
    const declineBtn = document.getElementById("declineCompliance");

    if (acceptBtn) {
      acceptBtn.addEventListener("click", () => {
        this.acceptCompliance();
      });
    }

    if (declineBtn) {
      declineBtn.addEventListener("click", () => {
        this.declineCompliance();
      });
    }
  }

  // Navigation
  navigateToSection(section) {
    console.log(`Navigating to section: ${section}`);

    // Update nav items
    document.querySelectorAll(".nav-item").forEach((item) => {
      item.classList.remove("active");
      if (item.dataset.section === section) {
        item.classList.add("active");
      }
    });

    // Update content sections
    document.querySelectorAll(".content-section").forEach((section_el) => {
      section_el.classList.remove("active");
    });

    const targetSection = document.getElementById(section);
    if (targetSection) {
      targetSection.classList.add("active");
    }

    this.currentSection = section;

    // Update send section summary when navigating to it
    if (section === "send") {
      this.updateSendSummary();
    }
  }

  // SMTP Configuration
  showSMTPModal(index = -1) {
    const modal = document.getElementById("smtpModal");
    const title = document.getElementById("smtpModalTitle");

    this.editingSmtpIndex = index;

    if (index >= 0 && this.smtpServers[index]) {
      // Edit existing server
      title.textContent = "Edit SMTP Server";
      const server = this.smtpServers[index];

      document.getElementById("smtpName").value = server.name || "";
      document.getElementById("smtpHost").value = server.host || "";
      document.getElementById("smtpPort").value = server.port || 587;
      document.getElementById("smtpUsername").value = server.username || "";
      document.getElementById("smtpPassword").value = server.password || "";
      document.getElementById("senderEmail").value = server.sender_email || "";
      document.getElementById("maxEmailsPerHour").value =
        server.max_emails_per_hour || 300;
      document.getElementById("smtpPriority").value = server.priority || 1;
      const encTLS = document.getElementById("encryptionTLS");
      const encSSL = document.getElementById("encryptionSSL");
      if (encTLS && encSSL) {
        if (server.use_ssl || server.port === 465) {
          encSSL.checked = true;
          encTLS.checked = false;
        } else {
          encTLS.checked = true;
          encSSL.checked = false;
        }
      }
      document.getElementById("smtpEnabled").checked = server.enabled !== false;
    } else {
      // Add new server
      title.textContent = "Add SMTP Server";
      document.getElementById("smtpForm").reset();
      document.getElementById("smtpPort").value = 587;
      document.getElementById("maxEmailsPerHour").value = 300;
      document.getElementById("smtpPriority").value =
        this.smtpServers.length + 1;
      const encTLS2 = document.getElementById("encryptionTLS");
      const encSSL2 = document.getElementById("encryptionSSL");
      if (encTLS2) encTLS2.checked = true;
      if (encSSL2) encSSL2.checked = false;
      document.getElementById("smtpEnabled").checked = true;
    }

    modal.style.display = "flex";
  }

  hideSMTPModal() {
    const modal = document.getElementById("smtpModal");
    modal.style.display = "none";
    this.editingSmtpIndex = -1;
  }

  async testSMTPConnection() {
    const formData = this.getSMTPFormData();
    if (!formData) return;

    this.showLoading();

    try {
      const response = await fetch("/api/test-smtp", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(formData),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const result = await response.json();

      if (result.success) {
        this.showNotification("SMTP connection successful!", "success");
      } else {
        this.showNotification(
          result.message || "Unknown error occurred",
          "error"
        );
      }
    } catch (error) {
      console.error("SMTP test error:", error);
      this.showNotification(
        `Failed to test SMTP connection: ${error.message}`,
        "error"
      );
    } finally {
      this.hideLoading();
    }
  }

  async testAllSMTPServers() {
    if (this.smtpServers.length === 0) {
      this.showNotification("No SMTP servers to test", "warning");
      return;
    }

    this.showLoading();

    try {
      const response = await fetch("/api/test-smtp", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(this.smtpServers),
      });

      const result = await response.json();

      if (result.success && result.results) {
        let successCount = 0;
        let failCount = 0;

        result.results.forEach((res) => {
          if (res.status === "success") successCount++;
          else failCount++;
        });

        this.showNotification(
          `Test Results: ${successCount} successful, ${failCount} failed`,
          failCount === 0 ? "success" : "warning"
        );
        this.addActivity(`Tested ${this.smtpServers.length} SMTP servers`);

        // Update server status in UI
        this.updateSMTPServersList();
      } else {
        this.showNotification(result.message || "Test failed", "error");
      }
    } catch (error) {
      console.error("SMTP test error:", error);
      this.showNotification("Failed to test SMTP servers", "error");
    } finally {
      this.hideLoading();
    }
  }

  saveSMTPServer() {
    const formData = this.getSMTPFormData();
    if (!formData) return;

    if (this.editingSmtpIndex >= 0) {
      // Update existing server
      this.smtpServers[this.editingSmtpIndex] = formData;
      this.showNotification("SMTP server updated successfully!", "success");
      this.addActivity(`Updated SMTP server: ${formData.name}`);
    } else {
      // Add new server
      this.smtpServers.push(formData);
      this.showNotification("SMTP server added successfully!", "success");
      this.addActivity(`Added SMTP server: ${formData.name}`);
    }

    // Auto-save to server
    this.saveSMTPServersToServer();

    this.updateSMTPServersList();
    this.updateDashboard();
    this.hideSMTPModal();
  }

  removeSMTPServer(index) {
    if (confirm("Are you sure you want to remove this SMTP server?")) {
      const server = this.smtpServers[index];
      this.smtpServers.splice(index, 1);
      this.updateSMTPServersList();
      this.updateDashboard();
      this.showNotification(`SMTP server "${server.name}" removed`, "success");
      this.addActivity(`Removed SMTP server: ${server.name}`);
    }
  }

  toggleSMTPServer(index) {
    const server = this.smtpServers[index];
    server.enabled = !server.enabled;
    this.updateSMTPServersList();
    this.updateDashboard();
    this.showNotification(
      `SMTP server "${server.name}" ${server.enabled ? "enabled" : "disabled"}`,
      "success"
    );
  }

  toggleRotationSettings(mode) {
    const emailCountSetting = document.getElementById("emailCountSetting");
    const timeDurationSetting = document.getElementById("timeDurationSetting");

    if (mode === "email_count") {
      emailCountSetting.style.display = "block";
      timeDurationSetting.style.display = "none";
    } else {
      emailCountSetting.style.display = "none";
      timeDurationSetting.style.display = "block";
    }
  }

  saveRotationSettings() {
    const mode = document.getElementById("rotationMode").value;
    const emailsPerRotation = parseInt(
      document.getElementById("emailsPerRotation").value
    );
    const secondsPerRotation = parseInt(
      document.getElementById("secondsPerRotation").value
    );
    const delayBetweenEmails = parseFloat(
      document.getElementById("delayBetweenEmails").value
    );
    const enableFailover = document.getElementById("enableFailover").checked;
    const maxRetries = parseInt(document.getElementById("maxRetries").value);

    this.rotationSettings = {
      mode,
      emailsPerRotation,
      secondsPerRotation,
      delayBetweenEmails,
      enableFailover,
      maxRetries,
    };

    this.showNotification("Rotation settings saved successfully!", "success");
    this.addActivity("Updated SMTP rotation settings");
    this.updateDashboard();
  }

  updateSMTPServersList() {
    const container = document.getElementById("smtpServersList");
    if (!container) return;

    if (this.smtpServers.length === 0) {
      container.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-server"></i>
                    <p>No SMTP servers configured</p>
                    <button class="btn btn-outline" id="addFirstSmtpBtn">Add Your First SMTP Server</button>
                </div>
            `;

      // Re-attach event listener
      const addFirstBtn = document.getElementById("addFirstSmtpBtn");
      if (addFirstBtn) {
        addFirstBtn.addEventListener("click", () => this.showSMTPModal());
      }
      return;
    }

    container.innerHTML = this.smtpServers
      .map(
        (server, index) => `
            <div class="smtp-server-card ${!server.enabled ? "disabled" : ""}">
                <div class="server-header">
                    <div class="server-info">
                        <h4>${server.name}</h4>
                        <span class="server-details">${server.host}:${
          server.port
        }</span>
                    </div>
                    <div class="server-actions">
                        <button class="btn btn-sm btn-outline" onclick="app.showSMTPModal(${index})" title="Edit">
                            <i class="fas fa-edit"></i>
                        </button>
                        <button class="btn btn-sm ${
                          server.enabled ? "btn-warning" : "btn-success"
                        }" 
                                onclick="app.toggleSMTPServer(${index})" title="${
          server.enabled ? "Disable" : "Enable"
        }">
                            <i class="fas fa-${
                              server.enabled ? "pause" : "play"
                            }"></i>
                        </button>
                        <button class="btn btn-sm btn-danger" onclick="app.removeSMTPServer(${index})" title="Remove">
                            <i class="fas fa-trash"></i>
                        </button>
                    </div>
                </div>
                <div class="server-stats">
                    <div class="stat">
                        <span class="stat-label">Priority</span>
                        <span class="stat-value">${server.priority || 1}</span>
                    </div>
                    <div class="stat">
                        <span class="stat-label">Max/Hour</span>
                        <span class="stat-value">${
                          server.max_emails_per_hour || 300
                        }</span>
                    </div>
                    <div class="stat">
                        <span class="stat-label">Status</span>
                        <span class="stat-value ${
                          server.enabled ? "status-enabled" : "status-disabled"
                        }">
                            ${server.enabled ? "Enabled" : "Disabled"}
                        </span>
                    </div>
                </div>
            </div>
        `
      )
      .join("");
  }

  getSMTPFormData() {
    const name = document.getElementById("smtpName")?.value?.trim();
    const host = document.getElementById("smtpHost")?.value?.trim();
    const port = parseInt(document.getElementById("smtpPort")?.value);
    const username = document.getElementById("smtpUsername")?.value?.trim();
    const password = document.getElementById("smtpPassword")?.value;
    const senderEmail = document.getElementById("senderEmail")?.value?.trim();
    const maxEmailsPerHour = parseInt(
      document.getElementById("maxEmailsPerHour")?.value
    );
    const priority = parseInt(document.getElementById("smtpPriority")?.value);
    const useTls = document.getElementById("useTls")?.checked;
    const enabled = document.getElementById("smtpEnabled")?.checked;

    if (!name || !host || !port || !username || !password || !senderEmail) {
      this.showNotification("Please fill in all required SMTP fields", "error");
      return null;
    }

    return {
      name,
      host,
      port,
      username,
      password,
      sender_email: senderEmail,
      max_emails_per_hour: maxEmailsPerHour || 300,
      priority: priority || 1,
      // Use radios if present; fallback to checkbox for backward compatibility
      use_tls: document.getElementById("encryptionTLS")?.checked ?? useTls,
      use_ssl: document.getElementById("encryptionSSL")?.checked ?? false,
      enabled: enabled,
    };
  }

  // Recipients Management
  async handleCSVUpload(file) {
    if (!file.name.endsWith(".csv")) {
      this.showNotification("Please upload a CSV file", "error");
      return;
    }

    const formData = new FormData();
    formData.append("file", file);

    this.showLoading();

    // Add timeout protection
    const controller = new AbortController();
    const timeoutId = setTimeout(() => {
      controller.abort();
      this.hideLoading();
      this.showNotification("Request timed out. Please try again.", "error");
    }, 30000); // 30 second timeout

    try {
      const response = await fetch("/api/upload-csv", {
        method: "POST",
        body: formData,
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const result = await response.json();

      if (result.success) {
        this.recipients = [...this.recipients, ...result.emails];

        // Auto-save to server
        this.saveEmailListsToServer();

        this.updateRecipientsTable();
        this.updateDashboard();
        this.showNotification(result.message, "success");
        this.addActivity(`Imported ${result.total_valid} recipients from CSV`);
      } else {
        this.showNotification(result.message || "Upload failed", "error");
      }
    } catch (error) {
      clearTimeout(timeoutId);
      if (error.name === "AbortError") {
        console.log("Request was aborted");
        return; // Don't show error message as we already showed timeout message
      }
      console.error("CSV upload error:", error);
      this.showNotification(
        `Failed to upload CSV file: ${error.message}`,
        "error"
      );
    } finally {
      this.hideLoading();
    }
  }

  async addManualEmails() {
    const manualEmails = document.getElementById("manualEmails")?.value?.trim();
    if (!manualEmails) {
      this.showNotification("Please enter email addresses", "error");
      return;
    }

    // Split by comma or newline
    const emails = manualEmails
      .split(/[,\n]/)
      .map((email) => email.trim())
      .filter((email) => email);

    this.showLoading();

    try {
      const response = await fetch("/api/validate-emails", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ emails }),
      });

      const result = await response.json();

      if (result.success) {
        // Add valid emails to recipients
        for (const emailObj of result.valid_emails) {
          if (!this.recipients.find((r) => r.email === emailObj.email)) {
            this.recipients.push(emailObj);
          }
        }

        // Auto-save to server
        this.saveEmailListsToServer();

        this.updateRecipientsTable();
        this.updateDashboard();
        document.getElementById("manualEmails").value = "";
        this.showNotification(
          `Added ${result.total_valid} valid emails`,
          "success"
        );
        this.addActivity(`Added ${result.total_valid} recipients manually`);

        if (result.total_invalid > 0) {
          this.showNotification(
            `Skipped ${result.total_invalid} invalid emails`,
            "warning"
          );
        }
      } else {
        this.showNotification(result.message, "error");
      }
    } catch (error) {
      console.error("Email validation error:", error);
      this.showNotification("Failed to validate emails", "error");
    } finally {
      this.hideLoading();
    }
  }

  async validateAllEmails() {
    if (this.recipients.length === 0) {
      this.showNotification("No recipients to validate", "warning");
      return;
    }

    const emails = this.recipients.map((r) => r.email);
    this.showLoading();

    try {
      const response = await fetch("/api/validate-emails", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ emails }),
      });

      const result = await response.json();

      if (result.success) {
        // Update recipients with validation status
        this.recipients = result.valid_emails;
        this.updateRecipientsTable();
        this.updateDashboard();
        this.showNotification(
          `Validated ${result.total_valid} emails`,
          "success"
        );

        if (result.total_invalid > 0) {
          this.showNotification(
            `Removed ${result.total_invalid} invalid emails`,
            "warning"
          );
        }
      } else {
        this.showNotification(result.message, "error");
      }
    } catch (error) {
      console.error("Validation error:", error);
      this.showNotification("Failed to validate emails", "error");
    } finally {
      this.hideLoading();
    }
  }

  clearAllRecipients() {
    if (this.recipients.length === 0) {
      this.showNotification("No recipients to clear", "warning");
      return;
    }

    if (confirm("Are you sure you want to clear all recipients?")) {
      this.recipients = [];
      this.updateRecipientsTable();
      this.updateDashboard();
      this.showNotification("All recipients cleared", "success");
      this.addActivity("All recipients cleared");
    }
  }

  updateRecipientsTable() {
    const tbody = document.querySelector("#recipientsTable tbody");
    if (!tbody) return;

    if (this.recipients.length === 0) {
      tbody.innerHTML = `
                <tr class="empty-state">
                    <td colspan="4">
                        <div class="empty-content">
                            <i class="fas fa-user-plus"></i>
                            <p>No recipients added yet</p>
                        </div>
                    </td>
                </tr>
            `;
      return;
    }

    tbody.innerHTML = this.recipients
      .map(
        (recipient, index) => `
            <tr>
                <td>${recipient.email}</td>
                <td>
                    <span class="status-${recipient.status || "valid"}">
                        <i class="fas fa-circle"></i>
                        ${recipient.status || "valid"}
                    </span>
                </td>
                <td>
                    ${
                      Object.keys(recipient)
                        .filter((k) => k !== "email" && k !== "status")
                        .map((k) => `${k}: ${recipient[k]}`)
                        .join(", ") || "-"
                    }
                </td>
                <td>
                    <button class="btn btn-sm btn-danger" onclick="app.removeRecipient(${index})">
                        <i class="fas fa-trash"></i>
                    </button>
                </td>
            </tr>
        `
      )
      .join("");
  }

  removeRecipient(index) {
    this.recipients.splice(index, 1);
    this.updateRecipientsTable();
    this.updateDashboard();
    this.showNotification("Recipient removed", "success");
  }

  // Email Composition
  switchEmailFormat(format) {
    const formatTabs = document.querySelectorAll(".format-tab");
    const htmlEditor = document.getElementById("emailBody");
    const plainEditor = document.getElementById("emailBodyPlain");
    const toolbar = document.getElementById("editorToolbar");

    if (!htmlEditor || !plainEditor || !toolbar) return;

    formatTabs.forEach((tab) => {
      tab.classList.remove("active");
      if (tab.dataset.format === format) {
        tab.classList.add("active");
      }
    });

    if (format === "html") {
      htmlEditor.style.display = "block";
      plainEditor.style.display = "none";
      toolbar.style.display = "flex";
    } else {
      htmlEditor.style.display = "none";
      plainEditor.style.display = "block";
      toolbar.style.display = "none";
    }

    this.updatePreview();
  }

  executeEditorCommand(action) {
    if (action === "insertImage") {
      this.saveEditorSelection();
      document.getElementById("inlineImageInput")?.click();
      return;
    }
    if (action === "createLink") {
      this.restoreEditorSelection();
      const selected = window.getSelection();
      if (!selected || selected.isCollapsed) {
        this.showNotification("Select text or an image first, then choose Link.", "info");
        return;
      }
      const url = prompt("Enter URL:");
      if (url) {
        try {
          const parsed = new URL(url, window.location.origin);
          if (!["https:", "http:", "mailto:", "tel:"].includes(parsed.protocol)) throw new Error("Unsupported link type");
          document.execCommand(action, false, url);
        } catch {
          this.showNotification("Use a valid http, https, email, or phone link.", "error");
        }
      }
    } else {
      this.restoreEditorSelection();
      document.execCommand(action, false, null);
    }
    this.saveEditorSelection();
    this.updatePreview();
  }

  renderEmailPreview(frame, body, isHtml) {
    if (!frame) return;
    let rendered = body || "<p>No content to preview</p>";
    if (isHtml) {
      rendered = rendered.replace(/src=(['\"])cid:([^'\"]+)\1/gi, (match, quote, id) => {
        const url = this.inlineImageUrls.get(id);
        return url ? `src=${quote}${url}${quote}` : match;
      });
    } else {
      rendered = rendered.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])).replace(/\n/g, "<br>");
    }
    frame.srcdoc = `<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>body{font:16px Arial,sans-serif;line-height:1.5;margin:16px;color:#222;overflow-wrap:anywhere}img{max-width:100%;height:auto}a{color:#1769c2}</style></head><body>${rendered}</body></html>`;
  }

  updatePreview() {
    const subject = document.getElementById("emailSubject")?.value || "";
    const activeTab = document.querySelector(".format-tab.active");
    const isHtml = activeTab ? activeTab.dataset.format === "html" : false;

    const body = isHtml
      ? document.getElementById("emailBody")?.innerHTML || ""
      : document.getElementById("emailBodyPlain")?.value || "";

    const previewSubject = document.getElementById("previewSubject");
    const previewBody = document.getElementById("previewBody");

    if (previewSubject) {
      previewSubject.textContent = subject || "No subject";
    }

    if (previewBody) {
      if (body.trim()) {
        this.renderEmailPreview(previewBody, body, isHtml);
      } else {
        this.renderEmailPreview(previewBody, "<p>Start typing to see preview</p>", true);
      }
    }
  }

  saveEmailContent() {
    const subject = document.getElementById("emailSubject")?.value?.trim();
    const activeTab = document.querySelector(".format-tab.active");
    const isHtml = activeTab ? activeTab.dataset.format === "html" : false;
    const body = isHtml
      ? document.getElementById("emailBody")?.innerHTML?.trim()
      : document.getElementById("emailBodyPlain")?.value?.trim();

    if (!subject || !body) {
      this.showNotification("Please fill in both subject and body", "error");
      return;
    }

    this.emailContent = { subject, body, is_html: isHtml };

    // Auto-save to server
    this.saveEmailTemplatesToServer();

    this.updateDashboard();
    this.showNotification("Email content saved successfully!", "success");
    this.addActivity("Email content composed and saved");
  }

  // Attachments
  async handleAttachmentUpload(file, { inline = false } = {}) {
    if (file.size > 50 * 1024 * 1024) {
      // 50MB limit
      this.showNotification("File size exceeds 50MB limit", "error");
      return;
    }
    const extension = file.name.split(".").pop().toLowerCase();
    if (!/[.](pdf|png|jpe?g|gif|webp|docx?|txt)$/i.test(file.name)) {
      this.showNotification("This file type is not supported.", "error");
      return;
    }
    if (inline && !["png", "jpg", "jpeg", "gif", "webp"].includes(extension)) {
      this.showNotification("Inline images must be PNG, JPEG, GIF, or WebP.", "error");
      return;
    }

    const formData = new FormData();
    formData.append("file", file);

    this.showLoading();

    try {
      const response = await fetch("/api/upload-attachment", {
        method: "POST",
        body: formData,
      });

      const result = await response.json();

      if (result.success) {
        const previewUrl = ["pdf", "png", "jpg", "jpeg", "gif", "webp"].includes(extension)
          ? URL.createObjectURL(file)
          : null;
        const savedFile = { ...result.file, inline, preview_url: previewUrl };
        this.attachments.push(savedFile);
        if (inline && previewUrl) this.inlineImageUrls.set(savedFile.id, previewUrl);
        this.updateAttachmentsGrid();
        this.updateDashboard();
        this.showNotification("File uploaded successfully", "success");
        this.addActivity(`Attached file: ${result.file.original_name}`);
        return savedFile;
      } else {
        this.showNotification(result.message, "error");
      }
    } catch (error) {
      console.error("Attachment upload error:", error);
      this.showNotification("Failed to upload file", "error");
    } finally {
      this.hideLoading();
    }
  }

  async insertInlineImage(file) {
    const attachment = await this.handleAttachmentUpload(file, { inline: true });
    if (!attachment) return;
    const editor = document.getElementById("emailBody");
    if (!editor) return;
    this.restoreEditorSelection();
    const image = document.createElement("img");
    image.src = `cid:${attachment.id}`;
    image.alt = file.name;
    image.dataset.inlineImageId = attachment.id;
    image.style.maxWidth = "100%";
    const range = window.getSelection()?.rangeCount ? window.getSelection().getRangeAt(0) : null;
    if (range && editor.contains(range.commonAncestorContainer)) {
      range.deleteContents();
      range.insertNode(image);
      range.setStartAfter(image);
      range.collapse(true);
      const selection = window.getSelection();
      selection.removeAllRanges();
      selection.addRange(range);
    } else {
      editor.appendChild(image);
    }
    this.saveEditorSelection();
    this.updatePreview();
  }

  updateAttachmentsGrid() {
    const grid = document.getElementById("attachmentsGrid");
    if (!grid) return;

    if (this.attachments.length === 0) {
      grid.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-paperclip"></i>
                    <p>No files attached</p>
                </div>
            `;
      return;
    }

    grid.innerHTML = this.attachments
      .map(
        (attachment, index) => `
            <div class="attachment-card">
                <button class="attachment-remove" onclick="app.removeAttachment(${index})">
                    <i class="fas fa-times"></i>
                </button>
                <div class="attachment-icon">
                    <i class="fas fa-${this.getFileIcon(
                      attachment.original_name
                    )}"></i>
                </div>
                <div class="attachment-name">${attachment.original_name}</div>
                <div class="attachment-size">${this.formatFileSize(
                  attachment.size
                )}</div>
                ${attachment.preview_url ? `<button class="btn btn-outline attachment-preview-button" onclick="app.previewAttachment(${index})">Preview</button>` : ""}
            </div>
        `
      )
      .join("");
  }

  removeAttachment(index) {
    const attachment = this.attachments[index];
    if (attachment.preview_url) URL.revokeObjectURL(attachment.preview_url);
    this.inlineImageUrls.delete(attachment.id);
    this.attachments.splice(index, 1);
    this.updateAttachmentsGrid();
    this.updateDashboard();
    this.showNotification("Attachment removed", "success");

    // Clean up file on server
    fetch("/api/cleanup-files", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ file_ids: [attachment.id] }),
    });
  }

  previewAttachment(index) {
    const file = this.attachments[index];
    if (!file?.preview_url) return;
    const modal = document.getElementById("attachmentPreviewModal");
    const title = document.getElementById("attachmentPreviewTitle");
    const frame = document.getElementById("attachmentPreviewFrame");
    const image = document.getElementById("attachmentPreviewImage");
    if (!modal || !frame || !image) return;
    title.textContent = file.original_name;
    const ext = file.original_name.split(".").pop().toLowerCase();
    if (ext === "pdf") {
      image.style.display = "none";
      frame.style.display = "block";
      frame.src = file.preview_url;
    } else {
      frame.style.display = "none";
      frame.src = "about:blank";
      image.src = file.preview_url;
      image.style.display = "block";
    }
    modal.style.display = "flex";
  }

  closeAttachmentPreview() {
    const modal = document.getElementById("attachmentPreviewModal");
    const frame = document.getElementById("attachmentPreviewFrame");
    if (modal) modal.style.display = "none";
    if (frame) frame.src = "about:blank";
  }

  getFileIcon(filename) {
    const ext = filename.split(".").pop().toLowerCase();
    const iconMap = {
      pdf: "file-pdf",
      doc: "file-word",
      docx: "file-word",
      txt: "file-alt",
      png: "file-image",
      jpg: "file-image",
      jpeg: "file-image",
      gif: "file-image",
    };
    return iconMap[ext] || "file";
  }

  formatFileSize(bytes) {
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
  }

  // Send Campaign
  updateSendSummary() {
    this.updateAdvancedPreview();
    this.updateLaunchButton();
  }

  updateAdvancedPreview() {
    // Email Content Preview
    const previewFrom = document.getElementById("previewFrom");
    const previewSubjectLine = document.getElementById("previewSubjectLine");
    const previewEmailBody = document.getElementById("previewEmailBody");

    if (previewFrom) {
      const enabledServers = this.smtpServers.filter((s) => s.enabled);
      previewFrom.textContent =
        enabledServers.length > 0
          ? enabledServers[0].sender_email
          : "No sender configured";
    }

    if (previewSubjectLine) {
      previewSubjectLine.textContent =
        this.emailContent?.subject || "No subject";
    }

    if (previewEmailBody) {
      if (this.emailContent?.body) {
        this.renderEmailPreview(previewEmailBody, this.emailContent.body, this.emailContent.is_html);
      } else {
        this.renderEmailPreview(previewEmailBody, "<p>No content to preview</p>", true);
      }
    }

    // Recipients Summary
    const totalRecipientsCount = document.getElementById(
      "totalRecipientsCount"
    );
    const domainBreakdown = document.getElementById("domainBreakdown");

    if (totalRecipientsCount) {
      totalRecipientsCount.textContent = this.recipients.length.toString();
    }

    if (domainBreakdown) {
      if (this.recipients.length > 0) {
        const domains = {};
        this.recipients.forEach((r) => {
          const domain = r.email.split("@")[1] || "unknown";
          domains[domain] = (domains[domain] || 0) + 1;
        });

        const sortedDomains = Object.entries(domains)
          .sort(([, a], [, b]) => b - a)
          .slice(0, 5);

        domainBreakdown.innerHTML = sortedDomains
          .map(
            ([domain, count]) =>
              `<div class="domain-item">
                        <span class="domain-name">${domain}</span>
                        <span class="domain-count">${count}</span>
                    </div>`
          )
          .join("");
      } else {
        domainBreakdown.innerHTML =
          '<div class="empty-breakdown">No recipients loaded</div>';
      }
    }

    // SMTP Summary
    const smtpSummary = document.getElementById("smtpSummary");
    if (smtpSummary) {
      const enabledServers = this.smtpServers.filter((s) => s.enabled);
      if (enabledServers.length > 0) {
        smtpSummary.innerHTML = `
                    <div class="smtp-overview">
                        <div class="smtp-stat">
                            <span class="stat-number">${
                              enabledServers.length
                            }</span>
                            <span class="stat-label">Active Servers</span>
                        </div>
                        <div class="smtp-rotation-info">
                            <span class="rotation-mode">${this.rotationSettings.mode.replace(
                              "_",
                              " "
                            )}</span>
                            <span class="rotation-value">
                                ${
                                  this.rotationSettings.mode === "email_count"
                                    ? `${this.rotationSettings.emailsPerRotation} emails`
                                    : `${this.rotationSettings.secondsPerRotation} seconds`
                                }
                            </span>
                        </div>
                    </div>
                    <div class="smtp-servers-preview">
                        ${enabledServers
                          .slice(0, 3)
                          .map(
                            (server) =>
                              `<div class="smtp-server-preview">
                                <span class="server-name">${server.name}</span>
                                <span class="server-priority">Priority ${server.priority}</span>
                            </div>`
                          )
                          .join("")}
                        ${
                          enabledServers.length > 3
                            ? `<div class="more-servers">+${
                                enabledServers.length - 3
                              } more</div>`
                            : ""
                        }
                    </div>
                `;
      } else {
        smtpSummary.innerHTML =
          '<div class="empty-smtp">No SMTP servers configured</div>';
      }
    }

    // Attachments Summary
    const attachmentsCount = document.getElementById("attachmentsCount");
    const attachmentsList = document.getElementById("attachmentsList");

    if (attachmentsCount) {
      attachmentsCount.textContent = this.attachments.length.toString();
    }

    if (attachmentsList) {
      if (this.attachments.length > 0) {
        attachmentsList.innerHTML = this.attachments
          .map(
            (att) =>
              `<div class="attachment-preview">
                        <span class="attachment-name">${
                          att.original_name
                        }</span>
                        <span class="attachment-size">${this.formatFileSize(
                          att.size
                        )}</span>
                    </div>`
          )
          .join("");
      } else {
        attachmentsList.innerHTML =
          '<div class="empty-attachments">No attachments</div>';
      }
    }
  }

  updateLaunchButton() {
    const enabledServers = this.smtpServers.filter((s) => s.enabled);
    const isReady =
      enabledServers.length > 0 &&
      this.emailContent &&
      this.recipients.length > 0;
    const launchBtn = document.getElementById("launchBtn");
    const launchWarning = document.getElementById("launchWarning");

    if (launchBtn) {
      if (isReady) {
        launchBtn.disabled = false;
        launchBtn.classList.remove("btn-secondary");
        launchBtn.classList.add("btn-danger");
        const span = launchBtn.querySelector("span");
        if (span) span.textContent = "Launch Campaign";

        if (launchWarning) launchWarning.style.display = "none";
      } else {
        launchBtn.disabled = true;
        launchBtn.classList.remove("btn-danger");
        launchBtn.classList.add("btn-secondary");
        const span = launchBtn.querySelector("span");
        if (span) span.textContent = "Complete Setup First";

        if (launchWarning) {
          launchWarning.style.display = "flex";
          const missing = [];
          if (enabledServers.length === 0) missing.push("SMTP servers");
          if (!this.emailContent) missing.push("email content");
          if (this.recipients.length === 0) missing.push("recipients");

          const warningSpan = launchWarning.querySelector("span");
          if (warningSpan) {
            warningSpan.textContent = `Missing: ${missing.join(", ")}`;
          }
        }
      }
    }
  }

  async launchCampaign() {
    // Validate setup
    const enabledServers = this.smtpServers.filter((s) => s.enabled);
    if (
      enabledServers.length === 0 ||
      !this.emailContent ||
      this.recipients.length === 0
    ) {
      this.showNotification("Please complete all setup steps first", "error");
      this.updateLaunchButton();
      return;
    }

    const sendModeElement = document.querySelector(
      'input[name="sendMode"]:checked'
    );
    const sendMode = sendModeElement ? sendModeElement.value : "dry_run";
    const isDryRun = sendMode === "dry_run";

    if (
      !isDryRun &&
      !confirm(
        `⚠️ Are you sure you want to send ${this.recipients.length} emails using ${enabledServers.length} SMTP server(s)? This action cannot be undone.`
      )
    ) {
      return;
    }

    // Show progress section
    const progressSection = document.getElementById("progressSection");
    const resultsSection = document.getElementById("resultsSection");

    if (progressSection) progressSection.style.display = "block";
    if (resultsSection) resultsSection.style.display = "none";

    // Reset progress
    this.resetProgress();

    // Get advanced options
    const batchSize =
      parseInt(document.getElementById("batchSize")?.value) || 50;
    const maxRetries =
      parseInt(document.getElementById("maxRetries")?.value) || 3;
    const enableAnalytics =
      document.getElementById("enableAnalytics")?.checked !== false;

    const payload = {
      smtp_configs: enabledServers, // Fixed: use array instead of single config
      content: this.emailContent,
      recipients: this.recipients,
      attachments: this.attachments,
      dry_run: isDryRun,
      rotation_mode: this.rotationSettings.mode,
      rotation_value:
        this.rotationSettings.mode === "email_count"
          ? this.rotationSettings.emailsPerRotation
          : this.rotationSettings.secondsPerRotation,
      delay_between_emails: this.rotationSettings.delayBetweenEmails,
      batch_size: batchSize,
      max_retries: maxRetries,
      enable_analytics: enableAnalytics,
    };

    try {
      this.startProgressTimer();

      const response = await fetch("/api/send-emails", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const result = await response.json();

      if (result.success) {
        let finalResults = result.results;
        if (result.job_id) {
          const started = Date.now();
          while (Date.now() - started < 15 * 60 * 1000) {
            await new Promise((resolve) => setTimeout(resolve, 500));
            const statusResponse = await fetch(`/api/send-status/${encodeURIComponent(result.job_id)}`);
            const status = await statusResponse.json();
            if (!statusResponse.ok || !status.success) throw new Error(status.message || "Could not read campaign status");
            if (status.results) this.updateProgressSnapshot(status.results);
            if (status.status === "complete") {
              finalResults = status.results;
              break;
            }
            if (status.status === "failed") throw new Error(status.error || "Campaign failed");
          }
          if (!finalResults) throw new Error("Campaign is still running; reopen the activity page to check its result.");
        }
        this.displayCampaignResults(finalResults);
        this.addActivity(
          `Campaign ${isDryRun ? "simulated" : "sent"}: ${
            finalResults.sent
          } emails`
        );
      } else {
        this.showNotification(result.message || "Campaign failed", "error");
      }
    } catch (error) {
      console.error("Campaign launch error:", error);
      this.showNotification("Failed to launch campaign", "error");
    } finally {
      this.stopProgressTimer();
    }
  }

  resetProgress() {
    const progressFill = document.getElementById("progressFill");
    const sentCount = document.getElementById("sentCount");
    const failedCount = document.getElementById("failedCount");
    const totalCount = document.getElementById("totalCount");
    const liveLog = document.getElementById("liveLog");

    if (progressFill) progressFill.style.width = "0%";
    if (sentCount) sentCount.textContent = "0";
    if (failedCount) failedCount.textContent = "0";
    if (totalCount) totalCount.textContent = this.recipients.length.toString();
    if (liveLog) liveLog.innerHTML = "";
  }

  updateProgressSnapshot(results) {
    const total = Number(results.total) || this.recipients.length || 0;
    const sent = Number(results.sent) || 0;
    const failed = Number(results.failed) || 0;
    const completed = Math.min(sent + failed, total);
    const percent = total ? (completed / total) * 100 : 0;
    const fill = document.getElementById("progressFill");
    const sentElement = document.getElementById("sentCount");
    const failedElement = document.getElementById("failedCount");
    const details = document.getElementById("progressDetails");
    if (fill) fill.style.width = `${percent}%`;
    if (sentElement) sentElement.textContent = String(sent);
    if (failedElement) failedElement.textContent = String(failed);
    if (details) details.textContent = `Processed ${completed} of ${total}`;
  }

  displayCampaignResults(results) {
    // Update progress bar
    const progressPercent =
      results.total > 0 ? (results.sent / results.total) * 100 : 0;

    const progressFill = document.getElementById("progressFill");
    const sentCount = document.getElementById("sentCount");
    const failedCount = document.getElementById("failedCount");

    if (progressFill) progressFill.style.width = progressPercent + "%";
    if (sentCount) sentCount.textContent = results.sent.toString();
    if (failedCount) failedCount.textContent = results.failed.toString();

    // Show results
    setTimeout(() => {
      const resultsSection = document.getElementById("resultsSection");
      if (resultsSection) {
        resultsSection.style.display = "block";

        const resultsContainer = document.getElementById("resultsContainer");
        if (resultsContainer) {
          resultsContainer.innerHTML = this.generateResultsHTML(results);
        }
      }
    }, 1000);
  }

  generateResultsHTML(results) {
    const duration = this.calculateDuration(
      results.start_time,
      results.end_time
    );

    let html = `
            <div class="results-summary">
                <div class="result-stat ${results.sent > 0 ? "success" : ""}">
                    <i class="fas fa-check-circle"></i>
                    <div>
                        <span class="result-number">${results.sent}</span>
                        <span class="result-label">Sent Successfully</span>
                    </div>
                </div>
                <div class="result-stat ${results.failed > 0 ? "error" : ""}">
                    <i class="fas fa-exclamation-circle"></i>
                    <div>
                        <span class="result-number">${results.failed}</span>
                        <span class="result-label">Failed</span>
                    </div>
                </div>
                <div class="result-stat">
                    <i class="fas fa-clock"></i>
                    <div>
                        <span class="result-number">${duration}</span>
                        <span class="result-label">Duration</span>
                    </div>
                </div>
            </div>
        `;

    if (results.dry_run) {
      html +=
        '<div class="dry-run-notice"><i class="fas fa-info-circle"></i> This was a test run - no emails were actually sent</div>';
    }

    if (results.failed_recipients && results.failed_recipients.length > 0) {
      html += `
                <div class="failed-recipients">
                    <h4>Failed Recipients</h4>
                    <ul>
                        ${results.failed_recipients
                          .slice(0, 5)
                          .map((fr) => `<li>${fr.email}: ${fr.error}</li>`)
                          .join("")}
                    </ul>
                    ${
                      results.failed_recipients.length > 5
                        ? `<p>... and ${
                            results.failed_recipients.length - 5
                          } more</p>`
                        : ""
                    }
                </div>
            `;
    }

    return html;
  }

  calculateDuration(start, end) {
    if (!start || !end) return "0s";
    const duration = new Date(end) - new Date(start);
    const seconds = Math.floor(duration / 1000);
    return seconds < 60
      ? `${seconds}s`
      : `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
  }

  startProgressTimer() {
    this.progressStartTime = Date.now();
    this.progressTimer = setInterval(() => {
      const elapsed = Math.floor((Date.now() - this.progressStartTime) / 1000);
      const elapsedTimeEl = document.getElementById("elapsedTime");
      if (elapsedTimeEl) {
        elapsedTimeEl.textContent =
          elapsed < 60
            ? `${elapsed}s`
            : `${Math.floor(elapsed / 60)}m ${elapsed % 60}s`;
      }
    }, 1000);
  }

  stopProgressTimer() {
    if (this.progressTimer) {
      clearInterval(this.progressTimer);
      this.progressTimer = null;
    }
  }

  resetProgress() {
    const progressFill = document.getElementById("progressFill");
    const progressText = document.getElementById("progressText");
    const sentCount = document.getElementById("sentCount");
    const failedCount = document.getElementById("failedCount");
    const elapsedTime = document.getElementById("elapsedTime");
    const rotationCount = document.getElementById("rotationCount");
    const progressDetails = document.getElementById("progressDetails");
    const liveLog = document.getElementById("liveLog");
    const currentSmtpName = document.getElementById("currentSmtpName");
    const currentSmtpUsage = document.getElementById("currentSmtpUsage");

    if (progressFill) progressFill.style.width = "0%";
    if (progressText) progressText.textContent = "0%";
    if (sentCount) sentCount.textContent = "0";
    if (failedCount) failedCount.textContent = "0";
    if (elapsedTime) elapsedTime.textContent = "0s";
    if (rotationCount) rotationCount.textContent = "0";
    if (progressDetails) progressDetails.textContent = "Initializing...";
    if (currentSmtpName) currentSmtpName.textContent = "-";
    if (currentSmtpUsage) currentSmtpUsage.textContent = "0 emails sent";

    if (liveLog) {
      liveLog.innerHTML = `
                <div class="log-entry initial">
                    <span class="log-time">${new Date().toLocaleTimeString()}</span>
                    <span class="log-message">Campaign initialized and ready to start...</span>
                </div>
            `;
    }
    const liveTable = document.getElementById("liveActivityTable");
    if (liveTable) liveTable.innerHTML = "";
  }

  displayCampaignResults(results) {
    this.stopProgressTimer();

    // Update final progress
    const progressPercent =
      results.total > 0 ? (results.sent / results.total) * 100 : 0;

    const progressFill = document.getElementById("progressFill");
    const progressText = document.getElementById("progressText");
    const sentCount = document.getElementById("sentCount");
    const failedCount = document.getElementById("failedCount");
    const progressDetails = document.getElementById("progressDetails");

    if (progressFill) progressFill.style.width = progressPercent + "%";
    if (progressText)
      progressText.textContent = Math.round(progressPercent) + "%";
    if (sentCount) sentCount.textContent = results.sent.toString();
    if (failedCount) failedCount.textContent = results.failed.toString();
    if (progressDetails) progressDetails.textContent = "Campaign completed!";
    // Populate live activity table and current SMTP summary from results
    this.renderLiveActivity(results);
    this.updateCurrentSmtpSummary(results);

    // Show detailed results after a delay
    setTimeout(() => {
      this.showDetailedResults(results);
    }, 1500);
  }

  updateCurrentSmtpSummary(results) {
    const nameEl = document.getElementById("currentSmtpName");
    const usageEl = document.getElementById("currentSmtpUsage");
    if (!nameEl || !usageEl) return;
    const activity = Array.isArray(results.activity) ? results.activity : [];
    const last = activity.length ? activity[activity.length - 1] : null;
    const currentName =
      results.current_smtp || (last ? last.smtp_server : "-") || "-";
    nameEl.textContent = currentName;
    const usage =
      results.smtp_usage && currentName in results.smtp_usage
        ? results.smtp_usage[currentName]
        : activity.filter(
            (a) => a.smtp_server === currentName && a.status === "sent"
          ).length;
    usageEl.textContent = `${usage} emails sent`;
  }

  renderLiveActivity(results) {
    const tbody = document.getElementById("liveActivityTable");
    if (!tbody) return;
    tbody.innerHTML = "";
    const activity = Array.isArray(results.activity) ? results.activity : [];
    const currentFilter =
      document.querySelector(".filter-chip.active")?.dataset.filter || "all";

    for (let i = activity.length - 1; i >= 0; i--) {
      const a = activity[i];
      const success = a.status === "sent";

      // Apply filtering
      if (currentFilter === "sent" && !success) continue;
      if (currentFilter === "failed" && success) continue;

      const icon = success
        ? '<i class="fas fa-check-circle" style="color:#22c55e"></i>'
        : '<i class="fas fa-times-circle" style="color:#ef4444"></i>';
      const time = a.timestamp
        ? new Date(a.timestamp).toLocaleTimeString()
        : new Date().toLocaleTimeString();
      const tr = document.createElement("tr");
      tr.dataset.status = success ? "sent" : "failed";
      tr.dataset.email = a.email || "";

      tr.innerHTML = `<td>${time}</td><td>${icon}</td><td>${
        a.email || "-"
      }</td><td>${(a.subject || "").toString().substring(0, 140)}</td><td>${
        a.smtp_server || "-"
      }</td><td>${a.error ? a.error.toString().substring(0, 200) : "-"}</td>
      <td>
        <button class="copy-email-btn" title="Copy email address" onclick="app.copyEmailToClipboard('${
          a.email || ""
        }')">
          <i class="fas fa-copy"></i>
        </button>
      </td>`;
      tbody.appendChild(tr);
    }
  }

  appendLiveActivity(email, success, detail = "") {
    const tbody = document.getElementById("liveActivityTable");
    if (!tbody) return;

    // Check if streaming is paused
    if (this.isPaused) return;

    // Check current filter
    const currentFilter =
      document.querySelector(".filter-chip.active")?.dataset.filter || "all";
    if (
      (currentFilter === "sent" && !success) ||
      (currentFilter === "failed" && success)
    ) {
      // Don't append if it doesn't match the current filter
      return;
    }

    const icon = success
      ? '<i class="fas fa-check-circle" style="color:#22c55e"></i>'
      : '<i class="fas fa-times-circle" style="color:#ef4444"></i>';
    const tr = document.createElement("tr");
    tr.dataset.status = success ? "sent" : "failed";
    tr.dataset.email = email || "";

    const time = new Date().toLocaleTimeString();
    const subject = this.emailContent?.subject || "";
    const currentSmtp =
      document.getElementById("currentSmtpName")?.textContent || "-";
    tr.innerHTML = `<td>${time}</td><td>${icon}</td><td>${email}</td><td>${subject}</td><td>${currentSmtp}</td><td>${
      detail || "-"
    }</td><td>
      <button class="copy-email-btn" title="Copy email address" onclick="app.copyEmailToClipboard('${
        email || ""
      }')">
        <i class="fas fa-copy"></i>
      </button>
    </td>`;
    tbody.prepend(tr);
  }

  showDetailedResults(results) {
    const resultsSection = document.getElementById("resultsSection");
    if (resultsSection) {
      resultsSection.style.display = "block";

      // Update summary cards
      const finalSentCount = document.getElementById("finalSentCount");
      const finalFailedCount = document.getElementById("finalFailedCount");
      const successPercentage = document.getElementById("successPercentage");
      const failurePercentage = document.getElementById("failurePercentage");
      const campaignDuration = document.getElementById("campaignDuration");
      const emailsPerMinute = document.getElementById("emailsPerMinute");
      const smtpServersUsed = document.getElementById("smtpServersUsed");
      const totalRotations = document.getElementById("totalRotations");

      if (finalSentCount) finalSentCount.textContent = results.sent.toString();
      if (finalFailedCount)
        finalFailedCount.textContent = results.failed.toString();

      const successRate =
        results.total > 0 ? (results.sent / results.total) * 100 : 0;
      const failureRate = 100 - successRate;

      if (successPercentage)
        successPercentage.textContent = successRate.toFixed(1) + "%";
      if (failurePercentage)
        failurePercentage.textContent = failureRate.toFixed(1) + "%";

      const duration = this.calculateDuration(
        results.start_time,
        results.end_time
      );
      if (campaignDuration) campaignDuration.textContent = duration;

      if (emailsPerMinute && results.start_time && results.end_time) {
        const durationMs =
          new Date(results.end_time) - new Date(results.start_time);
        const rate =
          durationMs > 0 ? Math.round((results.sent / durationMs) * 60000) : 0;
        emailsPerMinute.textContent = rate.toString();
      }

      if (smtpServersUsed) {
        const serversUsed = Object.keys(results.smtp_usage || {}).length;
        smtpServersUsed.textContent = serversUsed.toString();
      }

      if (totalRotations) {
        totalRotations.textContent = `${results.smtp_rotations || 0} rotations`;
      }

      // Update SMTP usage breakdown
      this.updateSmtpUsageBreakdown(results.smtp_usage || {});

      // Update failed recipients table
      this.updateFailedRecipientsTable(results.failed_recipients || []);
    }
  }

  updateSmtpUsageBreakdown(smtpUsage) {
    const smtpUsageGrid = document.getElementById("smtpUsageGrid");
    if (!smtpUsageGrid) return;

    if (Object.keys(smtpUsage).length === 0) {
      smtpUsageGrid.innerHTML =
        '<div class="empty-usage">No SMTP usage data</div>';
      return;
    }

    const total = Object.values(smtpUsage).reduce((a, b) => a + b, 0);

    smtpUsageGrid.innerHTML = Object.entries(smtpUsage)
      .sort(([, a], [, b]) => b - a)
      .map(([serverName, count]) => {
        const percentage = total > 0 ? (count / total) * 100 : 0;
        return `
                    <div class="smtp-usage-card">
                        <div class="usage-header">
                            <span class="server-name">${serverName}</span>
                            <span class="usage-count">${count} emails</span>
                        </div>
                        <div class="usage-bar">
                            <div class="usage-fill" style="width: ${percentage}%"></div>
                        </div>
                        <div class="usage-percentage">${percentage.toFixed(
                          1
                        )}%</div>
                    </div>
                `;
      })
      .join("");
  }

  updateFailedRecipientsTable(failedRecipients) {
    const failedRecipientsSection = document.getElementById(
      "failedRecipientsSection"
    );
    const failedRecipientsTable = document.getElementById(
      "failedRecipientsTable"
    );

    if (!failedRecipientsSection || !failedRecipientsTable) return;

    if (failedRecipients.length === 0) {
      failedRecipientsSection.style.display = "none";
      return;
    }

    failedRecipientsSection.style.display = "block";

    failedRecipientsTable.innerHTML = failedRecipients
      .map(
        (failed) => `
            <tr>
                <td>${failed.email}</td>
                <td class="error-reason">${failed.error}</td>
                <td>${failed.smtp_server || "Unknown"}</td>
                <td>${
                  failed.timestamp
                    ? new Date(failed.timestamp).toLocaleString()
                    : "-"
                }</td>
            </tr>
        `
      )
      .join("");
  }

  // Dashboard Updates
  updateDashboard() {
    // Update SMTP status
    const smtpStatus = document.getElementById("smtpStatus");
    if (smtpStatus) {
      const enabledServers = this.smtpServers.filter((s) => s.enabled);
      if (enabledServers.length > 0) {
        smtpStatus.innerHTML = `<i class="fas fa-circle status-success"></i><span>${enabledServers.length} Server(s) Ready</span>`;
      } else if (this.smtpServers.length > 0) {
        smtpStatus.innerHTML =
          '<i class="fas fa-circle status-warning"></i><span>Servers Disabled</span>';
      } else {
        smtpStatus.innerHTML =
          '<i class="fas fa-circle status-pending"></i><span>Not Configured</span>';
      }
    }

    // Update recipients status
    const recipientsStatus = document.getElementById("recipientsStatus");
    if (recipientsStatus) {
      if (this.recipients.length > 0) {
        recipientsStatus.innerHTML = `<i class="fas fa-circle status-success"></i><span>${this.recipients.length} Recipients</span>`;
      } else {
        recipientsStatus.innerHTML =
          '<i class="fas fa-circle status-pending"></i><span>0 Recipients</span>';
      }
    }

    // Update compose status
    const composeStatus = document.getElementById("composeStatus");
    if (composeStatus) {
      if (this.emailContent) {
        composeStatus.innerHTML =
          '<i class="fas fa-circle status-success"></i><span>Content Ready</span>';
      } else {
        composeStatus.innerHTML =
          '<i class="fas fa-circle status-pending"></i><span>Not Composed</span>';
      }
    }

    // Update launch status
    const launchStatus = document.getElementById("launchStatus");
    if (launchStatus) {
      const enabledServers = this.smtpServers.filter((s) => s.enabled);
      const isReady =
        enabledServers.length > 0 &&
        this.emailContent &&
        this.recipients.length > 0;
      if (isReady) {
        launchStatus.innerHTML =
          '<i class="fas fa-circle status-success"></i><span>Ready to Launch</span>';
      } else {
        launchStatus.innerHTML =
          '<i class="fas fa-circle status-pending"></i><span>Not Ready</span>';
      }
    }

    // Update sidebar stats
    const totalRecipients = document.getElementById("totalRecipients");
    const readyToSend = document.getElementById("readyToSend");

    if (totalRecipients)
      totalRecipients.textContent = this.recipients.length.toString();
    if (readyToSend) {
      const enabledServers = this.smtpServers.filter((s) => s.enabled);
      const isReady =
        enabledServers.length > 0 &&
        this.emailContent &&
        this.recipients.length > 0;
      readyToSend.textContent = isReady ? "Yes" : "No";
    }

    // Update send section if currently viewing it
    if (this.currentSection === "send") {
      this.updateSendSummary();
    }
  }

  addActivity(message) {
    const activityList = document.getElementById("activityList");
    if (!activityList) return;

    const time = new Date().toLocaleTimeString();

    const activityItem = document.createElement("div");
    activityItem.className = "activity-item";
    activityItem.innerHTML = `
            <i class="fas fa-check-circle"></i>
            <span>${message}</span>
            <time class="activity-time">${time}</time>
        `;

    activityList.insertBefore(activityItem, activityList.firstChild);

    // Keep only last 10 activities
    const activities = activityList.querySelectorAll(".activity-item");
    if (activities.length > 10) {
      activities[activities.length - 1].remove();
    }
  }

  // Compliance Modal
  showComplianceModal() {
    // Always hide loading overlay first
    this.hideLoading();

    const modal = document.getElementById("complianceModal");
    if (modal) {
      modal.style.display = "flex";
      modal.style.zIndex = "1004"; // Ensure it's above loading overlay
    }
  }

  acceptCompliance() {
    const modal = document.getElementById("complianceModal");
    if (modal) {
      modal.style.display = "none";
    }
    this.showNotification("Welcome to TermSender Pro!", "success");
    this.addActivity("Compliance agreement accepted");

    // Mark as accepted in session
    sessionStorage.setItem("complianceAccepted", "true");
  }

  declineCompliance() {
    const modal = document.getElementById("complianceModal");
    if (modal) {
      modal.style.display = "none";
    }
    this.showNotification(
      "You must agree to compliance terms to use TermSender Pro",
      "error"
    );

    // Redirect or close application
    setTimeout(() => {
      window.location.reload();
    }, 2000);
  }

  // UI Helpers
  showNotification(message, type = "info") {
    const container = document.getElementById("notificationContainer");
    if (!container) return;

    const notification = document.createElement("div");
    notification.className = `notification ${type}`;
    notification.textContent = message;

    container.appendChild(notification);

    // Auto remove after 5 seconds
    setTimeout(() => {
      if (notification.parentNode) {
        notification.parentNode.removeChild(notification);
      }
    }, 5000);
  }

  // Copy email to clipboard
  copyEmailToClipboard(email) {
    if (!email) return;

    navigator.clipboard
      .writeText(email)
      .then(() => {
        this.showNotification(`Email ${email} copied to clipboard`, "success");
      })
      .catch((err) => {
        console.error("Failed to copy email:", err);
        this.showNotification("Failed to copy email", "error");
      });
  }

  // Toggle pause/resume streaming
  togglePauseResume() {
    this.isPaused = !this.isPaused;
    const btn = document.getElementById("pauseResumeBtn");
    if (btn) {
      if (this.isPaused) {
        btn.innerHTML = '<i class="fas fa-play"></i> Resume Streaming';
        this.showNotification("Live activity streaming paused", "info");
      } else {
        btn.innerHTML = '<i class="fas fa-pause"></i> Pause Streaming';
        this.showNotification("Live activity streaming resumed", "success");
      }
    }
  }

  // Apply filter to the live activity table
  applyTableFilter(filter) {
    const rows = document.querySelectorAll("#liveActivityTable tr");

    rows.forEach((row) => {
      const status = row.dataset.status;

      if (filter === "all" || filter === status) {
        row.style.display = "";
      } else {
        row.style.display = "none";
      }
    });

    this.showNotification(`Showing ${filter} emails`, "info");
  }

  showLoading() {
    if (this.isLoading) return;
    this.isLoading = true;

    const overlay = document.getElementById("loadingOverlay");
    if (overlay) {
      overlay.style.display = "flex";
      overlay.style.zIndex = "1001";
    }
  }

  hideLoading() {
    this.isLoading = false;

    const overlay = document.getElementById("loadingOverlay");
    if (overlay) {
      overlay.style.display = "none";
    }

    // Force hide if stuck
    setTimeout(() => {
      if (overlay && overlay.style.display !== "none") {
        overlay.style.display = "none";
        this.isLoading = false;
      }
    }, 100);
  }

  // Data Persistence Methods
  async loadSavedData() {
    try {
      // Load SMTP servers
      const smtpResponse = await fetch("/api/config/smtp-servers");
      if (smtpResponse.ok) {
        const smtpData = await smtpResponse.json();
        if (smtpData.success) {
          this.smtpServers = smtpData.smtp_servers || [];
          this.updateSMTPServersList();
        }
      }

      // Load email lists
      const listsResponse = await fetch("/api/config/email-lists");
      if (listsResponse.ok) {
        const listsData = await listsResponse.json();
        if (listsData.success) {
          // Convert email lists to recipients format
          this.recipients = [];
          Object.values(listsData.email_lists || {}).forEach((list) => {
            this.recipients = [...this.recipients, ...list];
          });
          this.updateRecipientsTable();
        }
      }

      // Load email templates
      const templatesResponse = await fetch("/api/config/templates");
      if (templatesResponse.ok) {
        const templatesData = await templatesResponse.json();
        if (templatesData.success && templatesData.templates) {
          // Load the first template as default email content
          const templateNames = Object.keys(templatesData.templates);
          if (templateNames.length > 0) {
            const firstTemplate = templatesData.templates[templateNames[0]];
            this.emailContent = {
              subject: firstTemplate.subject,
              body: firstTemplate.body,
              is_html: firstTemplate.is_html || false,
            };
            const subjectInput = document.getElementById("emailSubject");
            if (subjectInput) subjectInput.value = firstTemplate.subject || "";
            this.switchEmailFormat(this.emailContent.is_html ? "html" : "plain");
            const editor = document.getElementById("emailBody");
            const plain = document.getElementById("emailBodyPlain");
            if (this.emailContent.is_html && editor) editor.innerHTML = firstTemplate.body || "";
            if (!this.emailContent.is_html && plain) plain.value = firstTemplate.body || "";
            this.updatePreview();
            this.updateAdvancedPreview();
          }
        }
      }

      console.log("Saved data loaded successfully");
    } catch (error) {
      console.error("Error loading saved data:", error);
    }
  }

  async saveSMTPServersToServer() {
    try {
      const response = await fetch("/api/config/smtp-servers", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ smtp_servers: this.smtpServers }),
      });

      if (!response.ok) {
        console.error("Failed to save SMTP servers");
      }
    } catch (error) {
      console.error("Error saving SMTP servers:", error);
    }
  }

  async saveEmailListsToServer() {
    try {
      // Convert recipients to email lists format
      const emailLists = {
        default: this.recipients,
      };

      const response = await fetch("/api/config/email-lists", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email_lists: emailLists }),
      });

      if (!response.ok) {
        console.error("Failed to save email lists");
      }
    } catch (error) {
      console.error("Error saving email lists:", error);
    }
  }

  async saveEmailTemplatesToServer() {
    try {
      if (!this.emailContent) return;

      const templates = {
        default: {
          subject: this.emailContent.subject,
          body: this.emailContent.body,
          is_html: this.emailContent.is_html || false,
          variables: [],
        },
      };

      const response = await fetch("/api/config/templates", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email_templates: templates }),
      });

      if (!response.ok) {
        console.error("Failed to save email templates");
      }
    } catch (error) {
      console.error("Error saving email templates:", error);
    }
  }
}

// Initialize app when DOM is loaded
document.addEventListener("DOMContentLoaded", () => {
  console.log("DOM loaded, initializing TermSender Pro...");
  window.app = new TermSenderApp();

  // Emergency cleanup for stuck loading states
  setTimeout(() => {
    const loadingOverlay = document.getElementById("loadingOverlay");
    if (loadingOverlay && loadingOverlay.style.display !== "none") {
      loadingOverlay.style.display = "none";
      console.log("Emergency cleanup: Forced loading overlay to hide");
    }
  }, 5000);
});

// Additional error handling
window.addEventListener("error", (e) => {
  console.error("JavaScript error:", e.error);
  // Hide loading on any JavaScript error
  const loadingOverlay = document.getElementById("loadingOverlay");
  if (loadingOverlay) {
    loadingOverlay.style.display = "none";
  }
});

// Handle page visibility changes
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible") {
    // Force hide loading when page becomes visible again
    const loadingOverlay = document.getElementById("loadingOverlay");
    if (loadingOverlay) {
      loadingOverlay.style.display = "none";
    }
    if (window.app) {
      window.app.isLoading = false;
    }
  }
});
