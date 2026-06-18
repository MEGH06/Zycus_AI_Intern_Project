# SSO / SAML Troubleshooting

## Common Causes of SSO Login Failures

1. **Expired SAML certificate** — Check your IdP certificate expiry date. Certificates must be renewed before expiry.
2. **Clock skew** — SAML assertions are time-sensitive. Ensure the IdP server clock is within 5 minutes of UTC.
3. **Incorrect ACS URL** — Verify the Assertion Consumer Service URL in your IdP matches the platform's configured ACS endpoint.
4. **Attribute mapping mismatch** — The `email` attribute must be mapped and non-empty in the SAML assertion.

## Resolution Steps

1. Re-download the SP metadata from Settings > SSO > Metadata.
2. Re-import into your IdP.
3. Test with a single user before rolling out to the team.
4. If issues persist, collect the SAML trace and attach it to your support ticket.
