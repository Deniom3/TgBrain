"""Сервис перезапуска Ingester."""
import asyncio
import logging
from asyncio import TimeoutError, wait_for
from typing import TYPE_CHECKING, Optional

from src.settings.repositories.encryption_settings import EncryptionKeyMismatchError
from src.settings.repositories.telegram_auth import TelegramAuthRepository

if TYPE_CHECKING:
    from src.protocols import IApplicationState

logger = logging.getLogger(__name__)

INGESTER_RESTART_DELAY_SECONDS = 2


class IngesterRestartService:

    RESTART_TIMEOUT_SECONDS = 60
    CREATE_TIMEOUT_SECONDS = 45

    @staticmethod
    async def stop_ingester(state: "IApplicationState") -> None:
        """
        Остановить текущий Ingester.

        Args:
            state: Состояние приложения через интерфейс IApplicationState
        """
        if hasattr(state, 'ingester') and state.ingester:
            logger.info("Остановка старого Ingester...")
            await state.ingester.stop()
            state.ingester = None  # type: ignore
            logger.info("Старый Ingester остановлен")

    @staticmethod
    async def create_new_ingester(state: "IApplicationState") -> bool:
        """
        Создать новый Ingester с сессией из БД.

        Args:
            state: Состояние приложения через интерфейс IApplicationState

        Returns:
            True если успешно создан и запущен
        """
        try:
            from src.config.loader import load_settings_from_db
            from src.ingestion import TelegramIngester

            new_settings = await load_settings_from_db()
            telegram_auth_repo = getattr(state, "telegram_auth_repo", None)
            if telegram_auth_repo is None:
                logger.error("TelegramAuthRepository не найден в state")
                return False

            app_settings_repo = getattr(state, "app_settings_repo", None)
            if app_settings_repo is None:
                logger.error("AppSettingsRepository не найден в state")
                return False

            new_ingester = TelegramIngester(
                new_settings,
                state.embeddings,  # type: ignore[arg-type]
                telegram_auth_repo,
                app_settings_repo,
                state.rate_limiter,
            )

            success = await new_ingester.reload_session()

            if success:
                state.ingester = new_ingester  # type: ignore
                polling_task = new_ingester.get_ingestion_task()
                if polling_task:
                    state.ingestion_task = polling_task  # type: ignore
                logger.info("Новый Ingester создан и запущен")
                return True
            else:
                logger.error("Не удалось запустить новый Ingester")
                return False

        except Exception:
            logger.error("Ошибка создания Ingester", exc_info=True)
            return False

    @staticmethod
    async def start_ingester(state: "IApplicationState") -> bool:
        """
        Запустить Ingester с сессией из БД.

        Args:
            state: Состояние приложения через интерфейс IApplicationState

        Returns:
            True если успешно запущен
        """
        try:
            if hasattr(state, 'ingester') and state.ingester and state.ingester.is_running():
                logger.info("Ingester уже запущен")
                return True

            if not hasattr(state, 'ingester') or state.ingester is None:
                from src.config.loader import load_settings_from_db
                from src.ingestion import TelegramIngester

                new_settings = await load_settings_from_db()
                telegram_auth_repo = getattr(state, "telegram_auth_repo", None)
                if telegram_auth_repo is None:
                    logger.error("TelegramAuthRepository не найден в state")
                    return False

                app_settings_repo = getattr(state, "app_settings_repo", None)
                if app_settings_repo is None:
                    logger.error("AppSettingsRepository не найден в state")
                    return False

                new_ingester = TelegramIngester(
                    new_settings,
                    state.embeddings,  # type: ignore[arg-type]
                    telegram_auth_repo,
                    app_settings_repo,
                    state.rate_limiter,
                )
                state.ingester = new_ingester  # type: ignore[misc]

            try:
                await wait_for(
                    state.ingester.start(),
                    timeout=60
                )
            except asyncio.TimeoutError:
                logger.error("Запуск Ingester превысил 60 секунд")
                return False

            if state.ingester.is_running():
                polling_task = state.ingester.get_ingestion_task()
                if polling_task:
                    state.ingestion_task = polling_task  # type: ignore[misc]
                logger.info("Ingester запущен")
                return True
            else:
                logger.error("Ingester не запустился (is_running=False)")
                return False

        except EncryptionKeyMismatchError:
            logger.error(
                "Обнаружена ошибка несоответствия ключа шифрования. "
                "Требуется повторная авторизация через QR-код."
            )
            return False
        except Exception as e:
            logger.error("Ошибка запуска Ingester: %s", e)
            return False

    @staticmethod
    async def restart(state: "IApplicationState") -> bool:
        """
        Перезапустить Ingester (полный цикл).

        Args:
            state: Состояние приложения через интерфейс IApplicationState

        Returns:
            True если успешно перезапущен
        """
        logger.info("Перезапуск Telegram Ingester...")

        try:
            await IngesterRestartService.stop_ingester(state)

            await asyncio.sleep(INGESTER_RESTART_DELAY_SECONDS)

            telegram_auth_repo: Optional[TelegramAuthRepository] = getattr(state, "telegram_auth_repo", None)
            if telegram_auth_repo is None:
                logger.error("TelegramAuthRepository не найден в state")
                return False

            auth = await telegram_auth_repo.get()

            if not auth or not auth.session_name:
                logger.error("Настройки Telegram не найдены в БД")
                return False

            success = await wait_for(
                IngesterRestartService.create_new_ingester(state),
                timeout=IngesterRestartService.CREATE_TIMEOUT_SECONDS
            )

            if not success:
                logger.error("Не удалось перезапустить Ingester")
                return False

            logger.info("Ingester успешно перезапущен")
            return True

        except TimeoutError:
            logger.error(
                "Перезапуск Ingester превысил %s секунд",
                IngesterRestartService.RESTART_TIMEOUT_SECONDS,
            )
            return False
        except Exception as e:
            logger.error("Критическая ошибка перезапуска Ingester: %s", e)
            return False

    @staticmethod
    async def stop_for_logout(state: "IApplicationState") -> bool:
        """
        Остановить Ingester для logout.

        Args:
            state: Состояние приложения через интерфейс IApplicationState

        Returns:
            True если успешно остановлен
        """
        logger.info("Остановка Ingester для logout...")

        await IngesterRestartService.stop_ingester(state)

        logger.info("Ingester остановлен (logout)")
        return True
