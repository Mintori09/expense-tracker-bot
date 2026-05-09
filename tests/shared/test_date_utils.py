"""Tests for Vietnamese date parsing utilities."""

import calendar
import pytest
from datetime import datetime, timedelta

from app.shared.date_utils import parse_vietnamese_date, resolve_relative_dates, extract_date_from_text


class TestParseVietnameseDate:
    """Tests for parse_vietnamese_date function."""
    
    def test_homo_qua_yesterday(self):
        """Test parsing 'hôm qua' (yesterday)."""
        today = datetime.now().date()
        expected = (today - timedelta(days=1)).strftime("%Y-%m-%d")
        
        result = parse_vietnamese_date("Ăn trưa hôm qua 85k")
        assert result == expected
    
    def test_hom_kia_day_before_yesterday(self):
        """Test parsing 'hôm kia' (day before yesterday)."""
        today = datetime.now().date()
        expected = (today - timedelta(days=2)).strftime("%Y-%m-%d")
        
        result = parse_vietnamese_date("Ăn tối hôm kia 120k")
        assert result == expected
    
    def test_ngay_mai_tomorrow(self):
        """Test parsing 'ngày mai' (tomorrow)."""
        today = datetime.now().date()
        expected = (today + timedelta(days=1)).strftime("%Y-%m-%d")
        
        result = parse_vietnamese_date("Coffee ngày mai 55k")
        assert result == expected
    
    def test_mong_mai_day_after_tomorrow(self):
        """Test parsing 'mống mai' (day after tomorrow)."""
        today = datetime.now().date()
        expected = (today + timedelta(days=2)).strftime("%Y-%m-%d")
        
        result = parse_vietnamese_date("Meeting mống mai 200k")
        assert result == expected
    
    def test_hom_nay_today(self):
        """Test parsing 'hôm nay' (today)."""
        today = datetime.now().date()
        expected = today.strftime("%Y-%m-%d")
        
        result = parse_vietnamese_date("Ăn sáng hôm nay 30k")
        assert result == expected
    
    def test_nay_today_short(self):
        """Test parsing 'nay' (today - short form)."""
        today = datetime.now().date()
        expected = today.strftime("%Y-%m-%d")
        
        result = parse_vietnamese_date("Chi phí nay 100k")
        assert result == expected
    
    def test_no_vietnamese_date(self):
        """Test text without Vietnamese date expressions."""
        result = parse_vietnamese_date("Ăn trưa 85k ở Phở Thìn")
        assert result is None
    
    def test_case_insensitive(self):
        """Test that parsing is case insensitive."""
        today = datetime.now().date()
        expected = (today - timedelta(days=1)).strftime("%Y-%m-%d")
        
        # Test uppercase
        result = parse_vietnamese_date("Ăn trưa HÔM QUA 85k")
        assert result == expected
        
        # Test mixed case
        result = parse_vietnamese_date("Ăn trưa HôM QuA 85k")
        assert result == expected
    
    def test_ngay_nay_thang_truoc(self):
        """Test parsing 'ngày này tháng trước' (same day of last month)."""
        today = datetime.now()
        year = today.year
        month = today.month - 1
        if month == 0:
            month = 12
            year -= 1
        
        # Calculate expected date
        day = min(today.day, calendar.monthrange(year, month)[1])
        expected = datetime(year, month, day).strftime("%Y-%m-%d")
        
        result = parse_vietnamese_date("Ăn trưa ngày này tháng trước 85k")
        assert result == expected
    
    def test_ngay_nay_tuan_truoc(self):
        """Test parsing 'ngày này tuần trước' (same weekday of last week)."""
        today = datetime.now()
        target = today - timedelta(weeks=1)
        expected = target.strftime("%Y-%m-%d")
        
        result = parse_vietnamese_date("Coffee ngày này tuần trước 55k")
        assert result == expected
    
    def test_ngay_nay_nam_truoc(self):
        """Test parsing 'ngày này năm trước' (same day of last year)."""
        today = datetime.now()
        
        # Handle Feb 29 case
        try:
            expected = datetime(today.year - 1, today.month, today.day).strftime("%Y-%m-%d")
        except ValueError:
            expected = datetime(today.year - 1, today.month, today.day - 1).strftime("%Y-%m-%d")
        
        result = parse_vietnamese_date("Ăn tối ngày này năm trước 120k")
        assert result == expected


class TestResolveRelativeDates:
    """Tests for resolve_relative_dates function."""
    
    def test_resolve_homo_qua(self):
        """Test resolving 'hôm qua' in text."""
        today = datetime.now().date()
        expected_date = (today - timedelta(days=1)).strftime("%Y-%m-%d")
        
        text, date_str = resolve_relative_dates("Ăn trưa hôm qua 85k")
        
        assert date_str == expected_date
        assert expected_date in text
        assert "hôm qua" not in text
    
    def test_resolve_preserves_rest(self):
        """Test that resolving preserves the rest of the text."""
        today = datetime.now().date()
        expected_date = (today + timedelta(days=1)).strftime("%Y-%m-%d")
        
        text, date_str = resolve_relative_dates("Coffee ngày mai tại The Coffee House 55k")
        
        assert "Coffee" in text
        assert "The Coffee House" in text
        assert "55k" in text
        assert date_str == expected_date
    
    def test_no_date_returns_none(self):
        """Test that text without relative dates returns None."""
        text, date_str = resolve_relative_dates("Ăn trưa 85k ở Phở Thìn")
        
        assert date_str is None
        assert text == "Ăn trưa 85k ở Phở Thìn"


class TestResolveRelativeDatesComplex:
    """Tests for resolve_relative_dates with complex patterns."""
    
    def test_resolve_ngay_nay_thang_truoc(self):
        """Test resolving 'ngày này tháng trước' in text."""
        today = datetime.now()
        
        year = today.year
        month = today.month - 1
        if month == 0:
            month = 12
            year -= 1
        day = min(today.day, calendar.monthrange(year, month)[1])
        expected_date = datetime(year, month, day).strftime("%Y-%m-%d")
        
        text, date_str = resolve_relative_dates("Ăn trưa ngày này tháng trước 85k")
        
        assert date_str == expected_date
        assert expected_date in text
    
    def test_resolve_ngay_nay_tuan_truoc(self):
        """Test resolving 'ngày này tuần trước' in text."""
        today = datetime.now()
        expected_date = (today - timedelta(weeks=1)).strftime("%Y-%m-%d")
        
        text, date_str = resolve_relative_dates("Coffee ngày này tuần trước 55k")
        
        assert date_str == expected_date
        assert expected_date in text
    
    def test_resolve_ngay_nay_nam_truoc(self):
        """Test resolving 'ngày này năm trước' in text."""
        today = datetime.now()
        try:
            expected_date = datetime(today.year - 1, today.month, today.day).strftime("%Y-%m-%d")
        except ValueError:
            expected_date = datetime(today.year - 1, today.month, today.day - 1).strftime("%Y-%m-%d")
        
        text, date_str = resolve_relative_dates("Ăn tối ngày này năm trước 120k")
        
        assert date_str == expected_date
        assert expected_date in text


class TestExtractDateFromText:
    """Tests for extract_date_from_text function."""
    
    def test_absolute_date_yyyy_mm_dd(self):
        """Test extracting absolute date in YYYY-MM-DD format."""
        result = extract_date_from_text("Ăn trưa 2025-01-15 85k")
        assert result == "2025-01-15"
    
    def test_absolute_date_dd_mm_yyyy(self):
        """Test extracting absolute date in DD/MM/YYYY format."""
        result = extract_date_from_text("Ăn trưa 15/01/2025 85k")
        assert result == "2025-01-15"
    
    def test_relative_date_priority(self):
        """Test that relative dates are used if no absolute date found."""
        today = datetime.now().date()
        expected = (today - timedelta(days=1)).strftime("%Y-%m-%d")
        
        result = extract_date_from_text("Ăn trưa hôm qua 85k")
        assert result == expected
    
    def test_no_date_returns_none(self):
        """Test that text without any date returns None."""
        result = extract_date_from_text("Ăn trưa 85k")
        assert result is None