"""agent/conflict_detector.py

Conflict detection between knowledge and reviews.
Detects contradictions in tool results.
"""

import re
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from agent.tools import ToolResult


@dataclass
class Conflict:
    """Represents a detected conflict."""
    conflict_type: str
    severity: str  # "high", "medium", "low"
    description: str
    sources: List[str]
    suggestion: str


class ConflictDetector:
    """Detects conflicts between knowledge and reviews."""
    
    def __init__(self):
        # Keywords for conflict detection
        self.warmth_keywords = {
            "positive": ["warm", "hot", "cozy", "insulated", "toasty", "perfect for winter"],
            "negative": ["cold", "chilly", "not warm", "insufficient", "freezing", "not insulated"]
        }
        
        self.sizing_keywords = {
            "positive": ["true to size", "fits well", "perfect fit", "as expected"],
            "negative": ["runs small", "runs large", "too tight", "too loose", "size up", "size down"]
        }
        
        self.quality_keywords = {
            "positive": ["high quality", "well made", "durable", "excellent", "great quality"],
            "negative": ["poor quality", "cheap", "flimsy", "falls apart", "defective"]
        }
    
    def detect_conflicts(self, tool_results: Dict[str, ToolResult]) -> List[Conflict]:
        """Detect conflicts in tool results.
        
        Args:
            tool_results: Dict of tool_name -> ToolResult
            
        Returns:
            List of detected conflicts
        """
        conflicts = []
        
        # Extract data from results
        knowledge_items = self._extract_knowledge(tool_results)
        reviews = self._extract_reviews(tool_results)
        
        if not knowledge_items or not reviews:
            return conflicts
        
        # Check for warmth conflicts
        warmth_conflict = self._check_warmth_conflict(knowledge_items, reviews)
        if warmth_conflict:
            conflicts.append(warmth_conflict)
        
        # Check for sizing conflicts
        sizing_conflict = self._check_sizing_conflict(knowledge_items, reviews)
        if sizing_conflict:
            conflicts.append(sizing_conflict)
        
        # Check for quality conflicts
        quality_conflict = self._check_quality_conflict(knowledge_items, reviews)
        if quality_conflict:
            conflicts.append(quality_conflict)
        
        # Check for skin sensitivity conflicts
        skin_conflict = self._check_skin_conflict(knowledge_items, reviews)
        if skin_conflict:
            conflicts.append(skin_conflict)
        
        return conflicts
    
    def _extract_knowledge(self, tool_results: Dict[str, ToolResult]) -> List[Dict]:
        """Extract knowledge items from tool results."""
        items = []
        if "knowledge_retrieval" in tool_results:
            result = tool_results["knowledge_retrieval"]
            if result.success and result.data:
                items.extend(result.data.get("knowledge_items", []))
        return items
    
    def _extract_reviews(self, tool_results: Dict[str, ToolResult]) -> List[Dict]:
        """Extract reviews from tool results."""
        reviews = []
        if "semantic_review_search" in tool_results:
            result = tool_results["semantic_review_search"]
            if result.success and result.data:
                data = result.data
                if "reviews" in data:
                    reviews.extend(data["reviews"])
                elif "groups" in data:
                    for group in data["groups"]:
                        reviews.extend(group.get("reviews", []))
        return reviews
    
    def _check_warmth_conflict(
        self,
        knowledge_items: List[Dict],
        reviews: List[Dict]
    ) -> Optional[Conflict]:
        """Check for conflicts in warmth claims."""
        # Check knowledge claims
        knowledge_warm = any(
            self._contains_keywords(item.get("content", ""), self.warmth_keywords["positive"]) or
            self._contains_keywords(item.get("warmth_range", ""), self.warmth_keywords["positive"])
            for item in knowledge_items
        )
        
        # Check review sentiments
        review_cold_count = sum(
            1 for review in reviews
            if self._contains_keywords(review.get("text", ""), self.warmth_keywords["negative"])
        )
        
        review_warm_count = sum(
            1 for review in reviews
            if self._contains_keywords(review.get("text", ""), self.warmth_keywords["positive"])
        )
        
        # Detect conflict: knowledge says warm but reviews say cold
        if knowledge_warm and review_cold_count > review_warm_count and review_cold_count >= 2:
            return Conflict(
                conflict_type="warmth",
                severity="high" if review_cold_count >= 3 else "medium",
                description=f"材料规格表明保暖性好，但{review_cold_count}条用户评价反映不够暖和",
                sources=["knowledge_retrieval", "semantic_review_search"],
                suggestion="向用户说明：虽然材料规格表明适合保暖，但部分用户反馈在极端寒冷环境下可能不够，建议根据实际使用场景考虑"
            )
        
        return None
    
    def _check_sizing_conflict(
        self,
        knowledge_items: List[Dict],
        reviews: List[Dict]
    ) -> Optional[Conflict]:
        """Check for conflicts in sizing claims."""
        # Analyze review sizing mentions
        small_count = sum(
            1 for review in reviews
            if self._contains_keywords(review.get("text", ""), ["runs small", "too small", "size up"])
        )
        
        large_count = sum(
            1 for review in reviews
            if self._contains_keywords(review.get("text", ""), ["runs large", "too large", "size down"])
        )
        
        # Detect conflict if significant skew
        total_sizing_mentions = small_count + large_count
        if total_sizing_mentions >= 3:
            if small_count > large_count * 2:
                return Conflict(
                    conflict_type="sizing",
                    severity="medium",
                    description=f"多数用户评价({small_count}条)反映尺码偏小",
                    sources=["semantic_review_search"],
                    suggestion="建议用户考虑选大一码"
                )
            elif large_count > small_count * 2:
                return Conflict(
                    conflict_type="sizing",
                    severity="medium",
                    description=f"多数用户评价({large_count}条)反映尺码偏大",
                    sources=["semantic_review_search"],
                    suggestion="建议用户考虑选小一码"
                )
        
        return None
    
    def _check_quality_conflict(
        self,
        knowledge_items: List[Dict],
        reviews: List[Dict]
    ) -> Optional[Conflict]:
        """Check for conflicts in quality claims."""
        # Check knowledge claims about quality
        knowledge_quality = any(
            self._contains_keywords(item.get("content", ""), ["high quality", "premium", "grade"])
            for item in knowledge_items
        )
        
        # Check negative quality reviews
        poor_quality_count = sum(
            1 for review in reviews
            if self._contains_keywords(review.get("text", ""), self.quality_keywords["negative"])
        )
        
        if knowledge_quality and poor_quality_count >= 2:
            return Conflict(
                conflict_type="quality",
                severity="medium",
                description=f"材料描述为高品质，但{poor_quality_count}条用户评价反映质量问题",
                sources=["knowledge_retrieval", "semantic_review_search"],
                suggestion="向用户呈现两方面信息：材料规格说明品质标准，但也有用户反馈质量问题，可能是个体差异"
            )
        
        return None
    
    def _check_skin_conflict(
        self,
        knowledge_items: List[Dict],
        reviews: List[Dict]
    ) -> Optional[Conflict]:
        """Check for conflicts in skin sensitivity claims."""
        # Check knowledge claims about skin safety
        knowledge_skin_safe = any(
            self._contains_keywords(item.get("skin_notes", ""), ["safe", "hypoallergenic", "gentle", "suitable for sensitive"])
            for item in knowledge_items
        )
        
        knowledge_skin_risk = any(
            self._contains_keywords(item.get("skin_notes", ""), ["may cause", "allergy", "irritation", "not suitable"])
            for item in knowledge_items
        )
        
        # Check review mentions
        irritation_count = sum(
            1 for review in reviews
            if self._contains_keywords(review.get("text", ""), ["itch", "rash", "irritation", "allergic", "sensitive"])
        )
        
        safe_count = sum(
            1 for review in reviews
            if self._contains_keywords(review.get("text", ""), ["no reaction", "gentle", "sensitive skin friendly", "no itch"])
        )
        
        # Detect conflicts
        if knowledge_skin_safe and irritation_count >= 2:
            return Conflict(
                conflict_type="skin_sensitivity",
                severity="high",
                description=f"材料说明对敏感肌安全，但{irritation_count}条用户评价报告过敏或刺激反应",
                sources=["knowledge_retrieval", "semantic_review_search"],
                suggestion="提醒用户：虽然材料通常对敏感肌友好，但个体差异存在，如有疑虑建议先小范围测试"
            )
        
        if knowledge_skin_risk and safe_count >= 2:
            return Conflict(
                conflict_type="skin_sensitivity",
                severity="low",
                description=f"材料说明可能有皮肤风险，但{safe_count}条敏感肌用户表示无不良反应",
                sources=["knowledge_retrieval", "semantic_review_search"],
                suggestion="说明材料理论上可能存在风险，但多位敏感肌用户实际使用无问题，风险较低"
            )
        
        return None
    
    def _contains_keywords(self, text: str, keywords: List[str]) -> bool:
        """Check if text contains any of the keywords (case insensitive)."""
        if not text:
            return False
        
        text_lower = text.lower()
        return any(keyword.lower() in text_lower for keyword in keywords)
    
    def format_conflicts(self, conflicts: List[Conflict]) -> str:
        """Format conflicts for inclusion in context."""
        if not conflicts:
            return ""
        
        lines = ["[CONFLICT DETECTION]"]
        lines.append("注意：发现以下信息矛盾，请向用户说明：\n")
        
        for i, conflict in enumerate(conflicts, 1):
            severity_icon = "⚠️" if conflict.severity == "high" else "⚡" if conflict.severity == "medium" else "ℹ️"
            lines.append(f"{severity_icon} 冲突 {i} ({conflict.conflict_type}):")
            lines.append(f"   问题：{conflict.description}")
            lines.append(f"   建议：{conflict.suggestion}\n")
        
        return "\n".join(lines)


def detect_conflicts(tool_results: Dict[str, ToolResult]) -> List[Conflict]:
    """Convenience function for conflict detection."""
    detector = ConflictDetector()
    return detector.detect_conflicts(tool_results)


def format_conflicts(conflicts: List[Conflict]) -> str:
    """Convenience function for formatting conflicts."""
    detector = ConflictDetector()
    return detector.format_conflicts(conflicts)
