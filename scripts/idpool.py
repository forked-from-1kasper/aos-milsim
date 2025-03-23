from itertools import count
from threading import Lock

class IDPool(set):
    """
    A thread-safe ID pool manager that allocates and deallocates unique IDs with advanced features.
    
    Args:
        start (int): The starting ID value (default: 0).
        step (int): The increment step between IDs (default: 1).
        max_id (int, optional): The maximum allowable ID; if exceeded, raises an error.
        reserved (iterable, optional): IDs that are reserved and cannot be allocated.
        logger (logging.Logger, optional): Logger instance for tracking ID operations.
    """
    def __init__(self, start=0, step=1, max_id=None, reserved=None, logger=None):
        self.start = start
        self.step = step
        self.max_id = max_id
        self.reserved = set(reserved) if reserved else set()
        self.logger = logger
        self.lock = Lock()  # Ensures thread-safe operations
        super().__init__()

    def pop(self):
        """
        Allocates and returns the next available ID that is neither in use nor reserved.
        
        Returns:
            int: The allocated ID.
            
        Raises:
            ValueError: If no IDs are available within the specified range.
        """
        with self.lock:
            # Generator expression to find the next available ID
            ID = next(ID for ID in count(self.start, self.step) 
                     if ID not in self and ID not in self.reserved)
            if self.max_id is not None and ID > self.max_id:
                raise ValueError("No more IDs available within the specified range")
            self.add(ID)
            if self.logger:
                self.logger.debug(f"Allocated ID: {ID}")
            return ID

    def put_back(self, ID):
        """
        Deallocates an ID, making it available for reuse.
        
        Args:
            ID: The ID to return to the pool.
        """
        with self.lock:
            if ID not in self:
                if self.logger:
                    self.logger.warning(f"Attempt to put back non-allocated ID: {ID}")
                return  # Silently ignore if ID wasn't allocated
            self.remove(ID)
            if self.logger:
                self.logger.debug(f"Deallocated ID: {ID}")

def apply_script(protocol, connection, config):
    """
    Extends a protocol with an enhanced IDPool instance, configurable via the config parameter.
    
    Args:
        protocol: The base protocol class to extend.
        connection: The connection object (passed through unchanged).
        config (dict): Configuration dictionary, with optional 'id_pool' key for IDPool settings.
        
    Returns:
        tuple: (Enhanced protocol class, connection)
    """
    class IDPoolProtocol(protocol):
        def __init__(self, *args, **kwargs):
            protocol.__init__(self, *args, **kwargs)
            # Extract ID pool configuration from config, if provided
            id_pool_config = config.get('id_pool', {})
            self.player_ids = IDPool(
                start=id_pool_config.get('start', 0),
                step=id_pool_config.get('step', 1),
                max_id=id_pool_config.get('max_id'),
                reserved=id_pool_config.get('reserved'),
                logger=getattr(self, 'logger', None)  # Use protocol's logger if available
            )

    return IDPoolProtocol, connection
