class MailCard extends HTMLElement {
  set hass(hass) {
    if (!this.content) {
      const card = document.createElement('ha-card');
      const link = document.createElement('link');
      link.type = 'text/css';
      link.rel = 'stylesheet';
      link.href = '/local/mail_and_packages/mail_and_packages.css?v=1';
      card.appendChild(link);
      this.content = document.createElement('div');
      this.content.className = 'mail-and-packages';
      card.appendChild(this.content);
      this.appendChild(card);
    }
    
    var curDatetime = new Date();
    var datetime = curDatetime.getMonth().toString() + curDatetime.getDate().toString() + curDatetime.getFullYear().toString() + curDatetime.getHours().toString() + curDatetime.getMinutes().toString();
    
    const in_transit = hass.states[this.config.in_transit].state;
    const deliver_today = hass.states[this.config.deliver_today].state;
    const summary = hass.states[this.config.summary].state;
    const ups = hass.states[this.config.ups].state;
    const fedex = hass.states[this.config.fedex].state;
    const usps = hass.states[this.config.usps].state;
    const mail = hass.states[this.config.mail].state;
    const last_update = hass.states[this.config.last_update].state;
    const mail_image = "/local/mail_and_packages/mail_today.gif" + "?v=" + datetime;

    this.content.innerHTML = `
            <div style="clear: both;">
           <span style="float: right;"><span class="mail-iron-icon"><iron-icon icon="mdi:package-variant"></iron-icon></span>Today's Deliveries: ${deliver_today}</span>
           <span class="mail-iron-icon"><iron-icon icon="mdi:truck-delivery"></iron-icon></span>In Transit: ${in_transit}
        </div>
        <br>
       ${summary}
	    <br>
      <span>
        <ul class="mail-variations right">
           <li><span class="mail-iron-icon"><iron-icon icon="mdi:package-variant-closed"></iron-icon></span><a href="https://wwwapps.ups.com/mcdp" title="Open the UPS MyChoice site" target="_blank">UPS: ${ups}</a></li>
           <br>
           <li><span class="mail-iron-icon"><iron-icon icon="mdi:package-variant-closed"></iron-icon></span><a href="https://www.fedex.com/apps/fedextracking" title="Open the Fedex site" target="_blank">Fedex: ${fedex}</a></li>
           <br>
        </ul>
        <ul class="mail-variations">
           <li><span class="mail-iron-icon"><iron-icon icon="mdi:email-outline"></iron-icon></span><a href="https://informeddelivery.usps.com/" title="Open the USPS Informed Delivery site" target="_blank">Mail: ${mail}<a></li>
           <br>
           <li><span class="mail-iron-icon"><iron-icon icon="mdi:package-variant-closed"></iron-icon></span><a href="https://informeddelivery.usps.com/" title="Open the USPS Informed Delivery site" target="_blank">USPS: ${usps}</a></li>
           <br>
        </ul>
      </span>
      <img class="MailImg clear" src="${mail_image}" />
      <span class="usps_update">Checked: ${last_update}</span>
    </div>`;
  }

  setConfig(config) {
    if (!config.mail || !config.usps) {
      throw new Error('Please define entities');
    }
    this.config = config;
  }

  // @TODO: This requires more intelligent logic
  getCardSize() {
    return 3;
  }
}

customElements.define('mail-and-packages', MailCard);
