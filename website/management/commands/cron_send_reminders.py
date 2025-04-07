import logging
import random
from itertools import islice

from django.conf import settings
from django.core.mail import EmailMessage
from django.utils import timezone

from website.management.base import LoggedBaseCommand
from website.models import ReminderSettings, UserProfile

logger = logging.getLogger("reminder_emails")
handler = logging.FileHandler("logs/reminder_emails.log")
handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logger.addHandler(handler)
logger.setLevel(logging.INFO)


def batch(iterable, size):
    """Helper function to create batches from an iterable"""
    iterator = iter(iterable)
    return iter(lambda: list(islice(iterator, size)), [])


class Command(LoggedBaseCommand):
    help = "Sends daily check-in reminders to users who haven't checked in today"

    def handle(self, *args, **options):
        try:
            now = timezone.now()
            logger.info(f"Starting reminder process at {now} (UTC)")

            # Calculate the current 15-minute window in UTC
            current_hour = now.hour
            current_minute = now.minute
            window_start_minute = (current_minute // 15) * 15
            window_end_minute = window_start_minute + 15

            # Handle minute overflow
            window_end_hour = current_hour
            if window_end_minute >= 60:
                window_end_minute = window_end_minute - 60
                window_end_hour = current_hour + 1
                if window_end_hour >= 24:
                    window_end_hour = 0

            # Convert to time objects for database filtering
            from datetime import time

            window_start_time = time(hour=current_hour, minute=window_start_minute)
            window_end_time = time(hour=window_end_hour, minute=window_end_minute)

            logger.info(f"Current UTC time: {now.strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info(
                f"Processing reminders for UTC time window: {window_start_time.strftime('%H:%M')} - {window_end_time.strftime('%H:%M')}"
            )
            logger.info(f"Time window in minutes: {window_start_minute} - {window_end_minute}")

            # Get active reminder settings within the current UTC time window
            # Exclude users who already received a reminder today
            active_settings = ReminderSettings.objects.filter(
                is_active=True, reminder_time_utc__gte=window_start_time, reminder_time_utc__lt=window_end_time
            ).exclude(last_reminder_sent__date=now.date())

            logger.info(f"Found {active_settings.count()} users with reminders in current UTC time window")

            users_needing_reminders = []

            for reminder_settings in active_settings:
                try:
                    # Check if user has checked in today
                    try:
                        profile = UserProfile.objects.get(user=reminder_settings.user)
                        last_checkin = profile.last_check_in
                        if last_checkin and last_checkin == now.date():
                            continue
                    except UserProfile.DoesNotExist:
                        pass

                    users_needing_reminders.append(reminder_settings.user)
                    logger.info(
                        f"User {reminder_settings.user.username} added to reminder list for time {reminder_settings.reminder_time} ({reminder_settings.timezone})"
                    )

                except Exception as e:
                    logger.error(f"Error processing user {reminder_settings.user.username}: {str(e)}")
                    continue

            if not users_needing_reminders:
                logger.info("No users need reminders at this time")
                return

            # Process users in batches of 50
            batch_size = 50
            successful_batches = 0
            failed_batches = 0
            total_users = len(users_needing_reminders)

            for i, user_batch in enumerate(batch(users_needing_reminders, batch_size), 1):
                try:
                    # Add random delay between batches (1-5 seconds)
                    if i > 1:
                        time.sleep(random.uniform(1, 5))

                    # Create email message
                    email = EmailMessage(
                        subject="Daily Check-in Reminder",
                        body="It's time for your daily check-in! Please log in to update your status.",
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        to=[settings.DEFAULT_FROM_EMAIL],  # Send to a single recipient
                        bcc=[user.email for user in user_batch],  # BCC all users in batch
                    )

                    # Send email
                    email.send()

                    # Update last_reminder_sent for successful batch
                    ReminderSettings.objects.filter(user_id__in=[user.id for user in user_batch]).update(
                        last_reminder_sent=now
                    )

                    successful_batches += 1
                    logger.info(f"Successfully sent batch {i} to {len(user_batch)} users")

                except Exception as e:
                    failed_batches += 1
                    logger.error(f"Error sending batch {i}: {str(e)}")

            # Log summary
            logger.info(
                f"""
            Reminder Summary:
            - Total users processed: {total_users}
            - Successful batches: {successful_batches}
            - Failed batches: {failed_batches}
            - Batch size: {batch_size}
            """
            )

            return f"Processed {total_users} users, {successful_batches} successful batches, {failed_batches} failed batches"
        except Exception as e:
            logger.error(f"Critical error in reminder process: {str(e)}")
            raise
