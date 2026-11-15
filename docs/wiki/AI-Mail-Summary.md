# AI-Powered Mail Summary

The integration generates a **grid image** (`sensor.mail_grid_image_path`) that arranges today's mail piece scans into a single PNG image grid. This grid image can be passed directly to vision-capable AI models to analyze envelopes, read senders and recipients, and produce a natural language summary of your incoming mail.

---

## Supported Postal Services for Mail Scans

- **USPS Informed Delivery** (`sensor.mail_usps_mail`) — United States
- **Deutsche Post** (`sensor.mail_post_de_mail`) — Germany

Depending on your configured postal service, when mail piece images are downloaded, the integration combines them into a grid image referenced by `sensor.mail_grid_image_path`.

---

## Option 1: LLM Vision Integration (`llmvision.image_analyzer`)

[LLM Vision](https://github.com/valentinfrlch/ha-llmvision) is a popular Home Assistant custom integration that allows you to analyze images using vision-capable AI providers (Google Gemini, OpenAI GPT-4o, Anthropic Claude, or local models via Ollama).

### Example Automation using LLM Vision

```yaml
alias: "Mail - LLM Vision Envelope Analysis"
description: "Analyzes today's mail grid image with LLM Vision to summarize incoming envelopes"
trigger:
  - platform: state
    entity_id: sensor.mail_grid_image_path
condition:
  - condition: template
    value_template: >-
      {{ states('sensor.mail_grid_image_path') not in ['unavailable', 'unknown', 'none', ''] }}
action:
  - action: llmvision.image_analyzer
    response_variable: mail_analysis
    data:
      provider: "YOUR_LLM_VISION_PROVIDER_ID"  # Replace with your LLM Vision provider ID
      image_file: "{{ states('sensor.mail_grid_image_path') }}"
      max_tokens: 150
      temperature: 0.2
      message: >-
        These are incoming mail envelopes.
        1. Identify the sender and recipient for each piece of mail visible in the image grid.
        2. Group the mail by recipient if there are multiple household members.
        3. Keep the entire response under 250 characters so it fits in a notification.

  - action: notify.mobile_app_your_phone
    data:
      title: "📬 Today's Mail Summary (AI)"
      message: "{{ mail_analysis.response_text }}"
      data:
        image: "/api/camera_proxy/camera.mail_usps_camera"
```

---

## Option 2: Core Home Assistant AI Tasks (`ai_task.generate_data`)

For native Home Assistant integrations (such as Google Generative AI / Gemini conversation agents) that support `ai_task.generate_data`:

```yaml
alias: "Daily Mail AI Summary"
description: "Natural language mail and package notifications using AI vision"
trigger:
  - platform: state
    entity_id:
      - sensor.mail_packages_delivered
      - sensor.mail_usps_mail
      - sensor.mail_packages_in_transit
    for:
      seconds: 5
  - platform: time
    at: "09:00:01"
condition:
  - condition: template
    value_template: >-
      {{ states('sensor.mail_grid_image_path') not in ['unavailable', 'unknown', 'none', ''] }}
action:
  - action: ai_task.generate_data
    data:
      task_name: Generate Daily Mail Summary
      entity_id: ai_task.YOUR_AI_ENTITY  # Replace with your AI task entity ID
      instructions: >-
        Examine the attached mail grid image and current package sensors:
        - Mail pieces today: {{ states('sensor.mail_usps_mail') | int(0) }}
        - Packages in transit: {{ states('sensor.mail_packages_in_transit') | int(0) }}
        - Delivered today: {{ states('sensor.mail_packages_delivered') | int(0) }}

        Summarize incoming senders and package deliveries in under 250 characters.
      attachments:
        - media_content_id: >-
            media-source://media_source/www/mail_and_packages/{{ states('sensor.mail_grid_image_path').split('/')[-1] }}
          media_content_type: image/png
    response_variable: ai_summary

  - action: notify.mobile_app_your_phone
    data:
      title: "📬 Today's Mail & Packages"
      message: "{{ ai_summary['data'] }}"
```

---

## Requirements & Sensor Reference

- **Image Storage**: The grid image PNG is written directly to the managed entry storage directory (`<config_dir>/mail_and_packages/<entry_id>/`). Local vision models and tools can read this image directly using the filesystem path provided by `sensor.mail_grid_image_path`.

Sensor | Description
--- | ---
`sensor.mail_grid_image_path` | Absolute filesystem path to today's collated mail grid PNG for your configured postal service (`usps_mail` or `post_de_mail`).
`sensor.mail_image_url` | Web URL to the rotating mail GIF.
`camera.mail_usps_camera` | Built-in camera entity showing mail scans.
