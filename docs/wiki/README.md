# Proposed wiki updates for #1578

GitHub wikis do not accept pull requests, so — as agreed in
[#1571](https://github.com/moralmunky/Home-Assistant-Mail-And-Packages/issues/1571)
and
[#1578](https://github.com/moralmunky/Home-Assistant-Mail-And-Packages/issues/1578) —
the proposed wiki markdown lives here in the repository, ready to
copy into the wiki git repository file for file. Each file is
named exactly like the wiki page it becomes. This `README.md` is
the only file here that is **not** a wiki page.

## Files

| File | Wiki action |
| --- | --- |
| `Amazon-Delivery-Confirmations.md` | **New page** — Amazon OTP/delivery-code sensors and recipes, attempted-delivery alert and self-clearing card, exception matching, midnight behavior |
| `Home.md` | Replace — adds the Delivery Confirmations feature bullet and the new page to the Wiki Documentation Index |
| `Notifications.md` | Replace — adds a short Amazon Delivery Codes and Attempted Deliveries section linking to the new page |
| `Configuration-and-Email-Settings.md` | Replace — adds a "Delivery-confirmation and Amazon code sensors" subsection under Step 2 (the sensor list) |
| `Supported-Shipper-Requirements.md` | Replace — DHL eCommerce attribution note, Shopify own-domain note, new eBay / PledgeBox / 4PX rows, and a short Delivery Confirmation Support Matrix section |

All sensor names, entity IDs, and attributes were checked against
`custom_components/mail_and_packages/const.py` and `sensor.py` on
`dev`, and the recipes are the corrected examples from #1571
(the earlier examples showed the entity state instead of the
code, appeared for `unknown`/`unavailable`, and could miss the
window-start reminder if the email was processed late).

Everything described has landed: the delivery-confirmation series
(#1575, #1577, #1579, #1580, #1582, #1581), the Amazon OTP work
(#1569, #1570), and PledgeBox / 4PX (#1584) are all merged.
Known gaps are stated as gaps — for example, there is no eBay,
PledgeBox, or 4PX delivered sensor yet, because no genuine
delivered sample is available to build one from.
