"""Supersede Workflow - Replace existing ADR with new decision."""

import os
import re
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime
from .base import BaseWorkflow, WorkflowResult, WorkflowStatus, WorkflowError
from .creation import CreationWorkflow, CreationInput
from .approval import ApprovalWorkflow, ApprovalInput
from ..core.model import ADR
from ..core.parse import find_adr_files, parse_adr_file


@dataclass
class SupersedeInput:
    """Input for ADR superseding workflow."""
    old_adr_id: str  # ADR to be superseded
    new_proposal: CreationInput  # New ADR proposal
    supersede_reason: str  # Why the old ADR is being replaced
    auto_approve: bool = False  # Whether to auto-approve the new ADR
    preserve_history: bool = True  # Whether to maintain bidirectional links


@dataclass
class SupersedeResult:
    """Result of ADR superseding."""
    old_adr_id: str
    new_adr_id: str
    old_adr_status: str  # Previous status of old ADR
    new_adr_status: str  # Status of new ADR
    relationships_updated: List[str]  # ADR IDs that had relationships updated
    automation_triggered: bool  # Whether approval automation was triggered
    conflicts_resolved: List[str]  # Conflicts that were resolved by superseding
    next_steps: str  # Guidance for what happens next


class SupersedeWorkflow(BaseWorkflow):
    """
    Supersede Workflow handles replacing existing ADRs with new decisions.
    
    This workflow manages the complex process of replacing an architectural
    decision while maintaining proper relationships and triggering automation.
    
    Workflow Steps:
    1. Validate that old ADR exists and can be superseded
    2. Create new ADR proposal using CreationWorkflow
    3. Update old ADR status to 'superseded'
    4. Update bidirectional relationships (supersedes/superseded_by)
    5. Update any ADRs that referenced the old ADR
    6. Optionally approve new ADR (triggering ApprovalWorkflow)
    7. Generate comprehensive superseding report
    """
    
    def execute(self, input_data: SupersedeInput) -> WorkflowResult:
        """Execute ADR superseding workflow."""
        try:
            # Step 1: Validate superseding preconditions
            old_adr, old_adr_file = self._validate_supersede_preconditions(input_data.old_adr_id)
            old_status = old_adr.status
            
            # Step 2: Create new ADR proposal
            creation_workflow = CreationWorkflow(adr_dir=self.adr_dir)
            creation_result = creation_workflow.execute(input_data.new_proposal)
            
            if creation_result.status != WorkflowStatus.SUCCESS:
                raise Exception(f"Failed to create new ADR: {creation_result.message}")
            
            new_adr_id = creation_result.data["creation_result"].adr_id
            
            # Step 3: Update old ADR to superseded status
            self._update_old_adr_status(old_adr, old_adr_file, new_adr_id, input_data.supersede_reason)
            
            # Step 4: Update new ADR with supersedes relationship
            self._update_new_adr_relationships(new_adr_id, input_data.old_adr_id)
            
            # Step 5: Update related ADRs
            updated_relationships = self._update_related_adr_relationships(
                input_data.old_adr_id, 
                new_adr_id
            )
            
            # Step 6: Resolve conflicts
            resolved_conflicts = self._resolve_conflicts_through_superseding(
                input_data.old_adr_id,
                creation_result.data["creation_result"].conflicts_detected
            )
            
            # Step 7: Optionally approve new ADR
            automation_triggered = False
            new_adr_status = "proposed"
            
            if input_data.auto_approve:
                approval_workflow = ApprovalWorkflow(adr_dir=self.adr_dir)
                approval_input = ApprovalInput(adr_id=new_adr_id, force_approve=True)
                approval_result = approval_workflow.execute(approval_input)
                
                if approval_result.status == WorkflowStatus.SUCCESS:
                    automation_triggered = True
                    new_adr_status = "accepted"
            
            # Step 8: Generate guidance
            next_steps = self._generate_supersede_guidance(
                new_adr_id, 
                automation_triggered, 
                resolved_conflicts
            )
            
            result = SupersedeResult(
                old_adr_id=input_data.old_adr_id,
                new_adr_id=new_adr_id,
                old_adr_status=old_status,
                new_adr_status=new_adr_status,
                relationships_updated=updated_relationships,
                automation_triggered=automation_triggered,
                conflicts_resolved=resolved_conflicts,
                next_steps=next_steps
            )
            
            return WorkflowResult(
                success=True,
                status=WorkflowStatus.SUCCESS,
                message=f"ADR {input_data.old_adr_id} superseded by {new_adr_id}",
                data={"supersede_result": result}
            )
            
        except Exception as e:
            result = WorkflowResult(
                success=False,
                status=WorkflowStatus.FAILED,
                message=f"Supersede workflow failed: {str(e)}"
            )
            result.add_error(f"SupersedeError: {str(e)}")
            return result
    
    def _validate_supersede_preconditions(self, old_adr_id: str) -> tuple[ADR, str]:
        """Validate that the old ADR exists and can be superseded."""
        adr_files = find_adr_files(self.adr_dir)
        
        for file_path in adr_files:
            try:
                adr = parse_adr_file(file_path)
                if adr.id == old_adr_id:
                    # Check if already superseded
                    if adr.status == "superseded":
                        raise ValueError(f"ADR {old_adr_id} is already superseded")
                    
                    return adr, file_path
            except Exception:
                continue
        
        raise ValueError(f"ADR {old_adr_id} not found in {self.adr_dir}")
    
    def _update_old_adr_status(
        self, 
        old_adr: ADR, 
        old_adr_file: str, 
        new_adr_id: str, 
        reason: str
    ) -> None:
        """Update old ADR status to superseded and add superseded_by relationship."""
        
        # Read current file content
        with open(old_adr_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Update status
        status_pattern = r'^status:\s*\w+$'
        content = re.sub(status_pattern, 'status: superseded', content, flags=re.MULTILINE)
        
        # Update or add superseded_by field
        superseded_by_pattern = r'^superseded_by:\s*.*$'
        superseded_by_line = f'superseded_by: ["{new_adr_id}"]'
        
        if re.search(superseded_by_pattern, content, flags=re.MULTILINE):
            # Replace existing superseded_by
            content = re.sub(superseded_by_pattern, superseded_by_line, content, flags=re.MULTILINE)
        else:
            # Add superseded_by before end of YAML front-matter
            yaml_end = content.find('\n---\n')
            if yaml_end != -1:
                supersede_metadata = (
                    f'{superseded_by_line}\n'
                    f'supersede_date: {datetime.now().strftime("%Y-%m-%d")}\n'
                    f'supersede_reason: "{reason}"\n'
                )
                content = content[:yaml_end] + supersede_metadata + content[yaml_end:]
        
        # Write updated content
        with open(old_adr_file, 'w', encoding='utf-8') as f:
            f.write(content)
    
    def _update_new_adr_relationships(self, new_adr_id: str, old_adr_id: str) -> None:
        """Update new ADR to include supersedes relationship."""
        adr_files = find_adr_files(self.adr_dir)
        
        for file_path in adr_files:
            try:
                adr = parse_adr_file(file_path)
                if adr.id == new_adr_id:
                    # Read and update file
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Update or add supersedes field
                    supersedes_pattern = r'^supersedes:\s*.*$'
                    supersedes_line = f'supersedes: ["{old_adr_id}"]'
                    
                    if re.search(supersedes_pattern, content, flags=re.MULTILINE):
                        # Replace existing supersedes
                        content = re.sub(supersedes_pattern, supersedes_line, content, flags=re.MULTILINE)
                    else:
                        # Add supersedes before end of YAML front-matter
                        yaml_end = content.find('\n---\n')
                        if yaml_end != -1:
                            content = content[:yaml_end] + supersedes_line + '\n' + content[yaml_end:]
                    
                    # Write updated content
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    
                    break
            except Exception:
                continue
    
    def _update_related_adr_relationships(self, old_adr_id: str, new_adr_id: str) -> List[str]:
        """Update any ADRs that referenced the old ADR."""
        updated_relationships = []
        adr_files = find_adr_files(self.adr_dir)
        
        for file_path in adr_files:
            try:
                adr = parse_adr_file(file_path)
                
                # Skip the ADRs we're already updating
                if adr.id in [old_adr_id, new_adr_id]:
                    continue
                
                # Check if this ADR references the old ADR
                needs_update = False
                content_to_update = None
                
                # Check supersedes relationships
                if old_adr_id in (adr.supersedes or []):
                    needs_update = True
                
                # Check superseded_by relationships
                if old_adr_id in (adr.superseded_by or []):
                    needs_update = True
                
                if needs_update:
                    # Read and update file
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Replace old ADR ID with new ADR ID in relationships
                    content = content.replace(f'"{old_adr_id}"', f'"{new_adr_id}"')
                    content = content.replace(f"'{old_adr_id}'", f"'{new_adr_id}'")
                    
                    # Write updated content
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    
                    updated_relationships.append(adr.id)
                
            except Exception:
                continue  # Skip problematic files
        
        return updated_relationships
    
    def _resolve_conflicts_through_superseding(
        self, 
        old_adr_id: str, 
        detected_conflicts: List[str]
    ) -> List[str]:
        """Resolve conflicts that existed with the old ADR."""
        resolved_conflicts = []
        
        # If the new ADR had conflicts with the old ADR, those are now resolved
        if old_adr_id in detected_conflicts:
            resolved_conflicts.append(old_adr_id)
        
        # Additional conflict resolution logic could be added here
        # For example, checking if superseding resolves policy conflicts
        
        return resolved_conflicts
    
    def _generate_supersede_guidance(
        self, 
        new_adr_id: str, 
        automation_triggered: bool, 
        resolved_conflicts: List[str]
    ) -> str:
        """Generate guidance for what happens next after superseding."""
        
        if automation_triggered:
            conflicts_text = ""
            if resolved_conflicts:
                conflicts_text = f" and resolved conflicts with {', '.join(resolved_conflicts)}"
            
            return (
                f"✅ Superseding complete! {new_adr_id} is now active{conflicts_text}. "
                f"All automation has been triggered and policies are being enforced. "
                f"The old decision is superseded and no longer active."
            )
        else:
            return (
                f"📋 Superseding complete! {new_adr_id} created but requires approval. "
                f"Use adr_approve('{new_adr_id}') to activate the new decision and "
                f"trigger policy enforcement. The old ADR is marked as superseded."
            )