import logging

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import (
    DataPart,
    InvalidParamsError,
    SendStreamingMessageSuccessResponse,
    Task,
    TaskArtifactUpdateEvent,
    TaskState,
    TaskStatusUpdateEvent,
    TextPart,
    UnsupportedOperationError,
)
from a2a.utils import new_agent_text_message, new_task
from a2a.utils.errors import ServerError
from common.base_agent import BaseAgent


logger = logging.getLogger(__name__)


class GenericAgentExecutor(AgentExecutor):
    """AgentExecutor used by the tragel agents."""

    def __init__(self, agent: BaseAgent):
        self.agent = agent

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        logger.info(f'Executing agent {self.agent.agent_name}')
        error = self._validate_request(context)
        if error:
            raise ServerError(error=InvalidParamsError())

        query = context.get_user_input()

        task = context.current_task

        if not task:
            task = new_task(context.message)
            await event_queue.enqueue_event(task)

        updater = TaskUpdater(event_queue, task.id, task.context_id)

        # Update task status to working at the start
        try:
            await updater.update_status(
                TaskState.working,
                new_agent_text_message(
                    f'{self.agent.agent_name}: Starting task...',
                    task.context_id,
                    task.id,
                ),
            )
        except Exception as e:
            logger.warning(f'Failed to send initial status update: {e}')

        try:
            async for item in self.agent.stream(query, task.context_id, task.id):
                # Agent to Agent call will return events,
                # Update the relevant ids to proxy back.
                if hasattr(item, 'root') and isinstance(
                    item.root, SendStreamingMessageSuccessResponse
                ):
                    event = item.root.result
                    if isinstance(
                        event,
                        (TaskStatusUpdateEvent | TaskArtifactUpdateEvent),
                    ):
                        await event_queue.enqueue_event(event)
                    continue

                is_task_complete = item['is_task_complete']
                require_user_input = item['require_user_input']

                if is_task_complete:
                    if item['response_type'] == 'data':
                        part = DataPart(data=item['content'])
                    else:
                        part = TextPart(text=item['content'])

                    await updater.add_artifact(
                        [part],
                        name=f'{self.agent.agent_name}-result',
                    )
                    await updater.complete()
                    break
                if require_user_input:
                    await updater.update_status(
                        TaskState.input_required,
                        new_agent_text_message(
                            item['content'],
                            task.context_id,
                            task.id,
                        ),
                        final=True,
                    )
                    break
                await updater.update_status(
                    TaskState.working,
                    new_agent_text_message(
                        item['content'],
                        task.context_id,
                        task.id,
                    ),
                )
        except Exception as e:
            # Log the full error with traceback for debugging
            logger.error(
                f'Error executing agent {self.agent.agent_name}: {e}',
                exc_info=True
            )
            
            # Try to update task status with error message
            error_message = f'Error: {str(e)}'
            # Truncate very long error messages
            if len(error_message) > 500:
                error_message = error_message[:500] + '...'
            
            try:
                await updater.update_status(
                    TaskState.working,  # Use working state as fallback if failed/error not available
                    new_agent_text_message(
                        f'{self.agent.agent_name} encountered an error: {error_message}',
                        task.context_id,
                        task.id,
                    ),
                    final=True,
                )
            except Exception as update_error:
                logger.error(
                    f'Failed to update task status with error: {update_error}',
                    exc_info=True
                )
            
            # Re-raise to let A2A framework handle it appropriately
            raise

    def _validate_request(self, context: RequestContext) -> bool:
        return False

    async def cancel(
        self, request: RequestContext, event_queue: EventQueue
    ) -> Task | None:
        raise ServerError(error=UnsupportedOperationError())
