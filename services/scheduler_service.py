import os
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from services.settings_service import SettingsService

class SchedulerService:
    _scheduler = None
    _started = False
    _last_run_at = None
    _last_result = None

    @classmethod
    def start(cls, flask_app):
        settings = SettingsService.load()
        scheduler_settings = settings.get("scheduler", {})

        if not scheduler_settings.get("enabled"):
            cls._started = False
            return

        # Flask debug reloader iki process çalıştırır. Scheduler'ı sadece child process'te başlat.
        # Yoksa bot aynı ürünü iki kez kontrol eder, sonra da masum gibi Telegram'a iki mesaj yollar.
        werkzeug_run_main = os.environ.get("WERKZEUG_RUN_MAIN")
        if werkzeug_run_main is not None and werkzeug_run_main != "true":
            return

        if cls._started:
            return

        interval_minutes = int(scheduler_settings.get("interval_minutes", 60))
        # Süreyi 1 dakikaya indirme limiti
        if interval_minutes < 1:
            interval_minutes = 1

        scheduler = BackgroundScheduler(daemon=True)

        def scheduled_job():
            with flask_app.app_context():
                from services.batch_check_service import BatchCheckService

                cls._last_run_at = datetime.now()
                cls._last_result = BatchCheckService.run_all_active_checks()

        scheduler.add_job(
            scheduled_job,
            trigger="interval",
            minutes=interval_minutes,
            id="shoehunter_batch_check",
            replace_existing=True,
            next_run_time=datetime.now(), # Uygulama açıldığında beklemeden hemen ilk kontrolü yapar
        )

        scheduler.start()

        cls._scheduler = scheduler
        cls._started = True

    @classmethod
    def status(cls):
        settings = SettingsService.load()
        scheduler_settings = settings.get("scheduler", {})

        next_run_time = None
        if cls._scheduler:
            job = cls._scheduler.get_job("shoehunter_batch_check")
            if job:
                next_run_time = job.next_run_time

        return {
            "enabled": bool(scheduler_settings.get("enabled")),
            "started": cls._started,
            "interval_minutes": int(scheduler_settings.get("interval_minutes", 60)),
            "next_run_time": next_run_time,
            "last_run_at": cls._last_run_at,
            "last_result": cls._last_result,
        }
