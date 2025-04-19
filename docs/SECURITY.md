# Security Best Practices for Abeille

This document provides security recommendations for running your Abeille instance.

## Bot Token Security

- **Never commit your Discord bot token** to version control.
- Store your token in environment variables or in `.env.local` files that are gitignored.
- Rotate your token if you suspect it has been compromised.
- Set appropriate bot permissions in the Discord Developer Portal.

## Pseudonymization Configuration

The bot uses pseudonymization to protect user identities. Configure these settings properly:

- Use a strong SALT value (at least 16 characters of random data)
- Choose an appropriate hash algorithm (SHA-256 or SHA-512 recommended)
- Set ITER to at least 100,000 for adequate protection

## Database Security

- Ensure your database files (in the `db/` folder) have proper file permissions
- Take regular backups of your database files
- Consider encrypting backups if storing them offsite
- Don't expose the database port if running in Docker

## Docker Security

If running in Docker (recommended):

- Keep the Docker image updated to the latest version.
- Don't run the container as root.
- Use Docker secrets for sensitive environment variables.
- Apply resource limits to the container.

## Admin Command Access

- Only give OWNER_ID status to trusted administrators
- Be cautious when using admin commands that affect data
- Regularly audit who has access to admin capabilities

## Discord Server Configuration

- Use Discord's built-in permission system to restrict which channels the bot can access
- Create a dedicated role for the bot with only the permissions it needs
- Regularly review the bot's permissions

## Maintenance

- Keep the bot code and dependencies updated
- Monitor logs for suspicious activity
- Implement rate limiting for commands that might be abused

## Privacy Considerations

- Inform server members about data collection
- Respect privacy opt-out requests
- Delete data when requested in accordance with privacy regulations
- Document your data retention policies
