"""
Сервис шифрования/расшифрования session_data.

Infrastructure сервис для безопасной работы с сессионными данными.
"""

from cryptography.fernet import Fernet


class SessionDecryptionService:
    """
    Сервис шифрования/расшифрования session_data.
    
    Использует Fernet (symmetric encryption) для шифрования
    сессионных данных Telegram.
    
    Example:
        # Шифрование
        encrypted = SessionDecryptionService.encrypt(session_data, key)
        
        # Расшифрование
        decrypted = SessionDecryptionService.decrypt(encrypted, key)
    """
    
    @staticmethod
    def encrypt(session_data: bytes, key: bytes) -> bytes:
        """
        Зашифровать session_data.
        
        Args:
            session_data: Данные сессии для шифрования.
            key: Ключ шифрования (32 байта, base64-encoded).
            
        Returns:
            Зашифрованные данные (Fernet token).
        """
        f = Fernet(key)
        return f.encrypt(session_data)
    
    @staticmethod
    def decrypt(encrypted_data: bytes, key: bytes) -> bytes:
        """
        Расшифровать session_data.
        
        Args:
            encrypted_data: Зашифрованные данные (Fernet token).
            key: Ключ расшифрования (32 байта, base64-encoded).
            
        Returns:
            Расшифрованные данные сессии.
            
        Raises:
            cryptography.fernet.InvalidToken: Если ключ неверный или данные повреждены.
        """
        f = Fernet(key)
        return f.decrypt(encrypted_data)
    
    @staticmethod
    def is_encrypted(data: bytes) -> bool:
        """
        Проверить, зашифрованы ли данные.
        
        Fernet токены начинаются с 'gAAAAA' (base64 encoded version).
        
        Args:
            data: Данные для проверки.
            
        Returns:
            True если данные зашифрованы.
        """
        return data.startswith(b"gAAAAA")
