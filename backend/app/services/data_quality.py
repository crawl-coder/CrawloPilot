"""
Phase 5: 数据质量检测服务
"""
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from app.models.data_quality import DataQualityCheck, DataQualityRule, DataStatistics, DataQualityStatus
from app.models import TaskInstance, TaskStatus


class DataQualityService:
    """数据质量检测服务"""
    
    @staticmethod
    def create_quality_check(
        db: Session,
        task_instance_id: int,
        project_id: int,
        spider_name: str,
        quality_data: Dict
    ) -> DataQualityCheck:
        """创建数据质量检测记录"""
        check = DataQualityCheck(
            task_instance_id=task_instance_id,
            project_id=project_id,
            spider_name=spider_name,
            **quality_data
        )
        db.add(check)
        db.commit()
        db.refresh(check)
        return check
    
    @staticmethod
    def evaluate_quality(
        total_records: int,
        null_fields: Dict,
        duplicate_count: int,
        format_errors: Dict,
        data_freshness: int,
        rules: Optional[Dict] = None
    ) -> Dict:
        """评估数据质量并返回检测结果"""
        if rules is None:
            rules = {
                'min_records': 0,
                'max_records': None,
                'null_rate_threshold': 0.1,
                'duplicate_rate_threshold': 0.05,
                'freshness_threshold': 86400  # 24小时
            }
        
        # 1. 数据量检测
        records_in_range = total_records >= rules.get('min_records', 0)
        if rules.get('max_records'):
            records_in_range = records_in_range and (total_records <= rules['max_records'])
        
        # 2. 空值率检测
        null_rate_passed = True
        null_rate_threshold = rules.get('null_rate_threshold', 0.1)
        for field_name, field_data in null_fields.items():
            if field_data.get('null_rate', 0) > null_rate_threshold:
                null_rate_passed = False
                break
        
        # 3. 重复率检测
        duplicate_rate = (duplicate_count / total_records * 100) if total_records > 0 else 0
        duplicate_rate_threshold = rules.get('duplicate_rate_threshold', 5)
        duplicate_passed = duplicate_rate <= duplicate_rate_threshold
        
        # 4. 格式校验
        format_passed = len(format_errors) == 0
        
        # 5. 时效性检测
        freshness_threshold = rules.get('freshness_threshold', 86400)
        freshness_passed = data_freshness <= freshness_threshold
        
        # 计算总体评分
        score = 100.0
        if not records_in_range:
            score -= 30
        if not null_rate_passed:
            score -= 20
        if not duplicate_passed:
            score -= 25
        if not format_passed:
            score -= 15
        if not freshness_passed:
            score -= 10
        
        score = max(0, score)
        
        # 确定总体状态
        if score >= 80:
            overall_status = DataQualityStatus.PASSED
        elif score >= 60:
            overall_status = DataQualityStatus.WARNING
        else:
            overall_status = DataQualityStatus.FAILED
        
        return {
            'total_records': total_records,
            'expected_min_records': rules.get('min_records'),
            'expected_max_records': rules.get('max_records'),
            'records_in_range': records_in_range,
            'null_fields': null_fields,
            'null_rate_threshold': null_rate_threshold,
            'null_rate_passed': null_rate_passed,
            'duplicate_count': duplicate_count,
            'duplicate_rate': round(duplicate_rate, 2),
            'duplicate_rate_threshold': duplicate_rate_threshold,
            'duplicate_passed': duplicate_passed,
            'format_errors': format_errors,
            'format_passed': format_passed,
            'data_freshness': data_freshness,
            'freshness_threshold': freshness_threshold,
            'freshness_passed': freshness_passed,
            'overall_status': overall_status,
            'score': round(score, 2),
            'details': {
                'checks': {
                    'record_count': {'passed': records_in_range, 'score': 30 if records_in_range else 0},
                    'null_rate': {'passed': null_rate_passed, 'score': 20 if null_rate_passed else 0},
                    'duplicate_rate': {'passed': duplicate_passed, 'score': 25 if duplicate_passed else 0},
                    'format': {'passed': format_passed, 'score': 15 if format_passed else 0},
                    'freshness': {'passed': freshness_passed, 'score': 10 if freshness_passed else 0}
                }
            }
        }
    
    @staticmethod
    def get_quality_checks(
        db: Session,
        project_id: Optional[int] = None,
        spider_name: Optional[str] = None,
        status: Optional[DataQualityStatus] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 50
    ) -> List[DataQualityCheck]:
        """获取数据质量检测记录"""
        query = db.query(DataQualityCheck)
        
        if project_id:
            query = query.filter(DataQualityCheck.project_id == project_id)
        if spider_name:
            query = query.filter(DataQualityCheck.spider_name == spider_name)
        if status:
            query = query.filter(DataQualityCheck.overall_status == status)
        if start_date:
            query = query.filter(DataQualityCheck.checked_at >= start_date)
        if end_date:
            query = query.filter(DataQualityCheck.checked_at <= end_date)
        
        query = query.order_by(DataQualityCheck.checked_at.desc())
        return query.offset(skip).limit(limit).all()
    
    @staticmethod
    def get_quality_stats(
        db: Session,
        project_id: Optional[int] = None,
        days: int = 30
    ) -> Dict:
        """获取数据质量统计"""
        start_date = datetime.utcnow() - timedelta(days=days)
        
        query = db.query(DataQualityCheck).filter(DataQualityCheck.checked_at >= start_date)
        if project_id:
            query = query.filter(DataQualityCheck.project_id == project_id)
        
        total = query.count()
        passed = query.filter(DataQualityCheck.overall_status == DataQualityStatus.PASSED).count()
        warning = query.filter(DataQualityCheck.overall_status == DataQualityStatus.WARNING).count()
        failed = query.filter(DataQualityCheck.overall_status == DataQualityStatus.FAILED).count()
        
        avg_score = db.query(func.avg(DataQualityCheck.score)).filter(
            DataQualityCheck.checked_at >= start_date
        )
        if project_id:
            avg_score = avg_score.filter(DataQualityCheck.project_id == project_id)
        
        avg_score_result = avg_score.scalar() or 0
        
        return {
            'total_checks': total,
            'passed': passed,
            'warning': warning,
            'failed': failed,
            'pass_rate': round((passed / total * 100) if total > 0 else 0, 2),
            'average_score': round(float(avg_score_result), 2)
        }


class DataStatisticsService:
    """数据统计服务"""
    
    @staticmethod
    def record_statistics(
        db: Session,
        project_id: int,
        spider_name: str,
        task_instance_id: int,
        stats_data: Dict
    ) -> DataStatistics:
        """记录统计数据"""
        stat = DataStatistics(
            project_id=project_id,
            spider_name=spider_name,
            task_instance_id=task_instance_id,
            **stats_data
        )
        db.add(stat)
        db.commit()
        db.refresh(stat)
        return stat
    
    @staticmethod
    def get_project_statistics(
        db: Session,
        project_id: int,
        stat_type: str = 'daily',
        days: int = 30
    ) -> List[DataStatistics]:
        """获取项目统计数据"""
        start_date = datetime.utcnow() - timedelta(days=days)
        
        return db.query(DataStatistics).filter(
            and_(
                DataStatistics.project_id == project_id,
                DataStatistics.stat_date >= start_date,
                DataStatistics.stat_type == stat_type
            )
        ).order_by(DataStatistics.stat_date.asc()).all()
    
    @staticmethod
    def get_spider_statistics(
        db: Session,
        project_id: int,
        spider_name: str,
        days: int = 30
    ) -> List[DataStatistics]:
        """获取爬虫统计数据"""
        start_date = datetime.utcnow() - timedelta(days=days)
        
        return db.query(DataStatistics).filter(
            and_(
                DataStatistics.project_id == project_id,
                DataStatistics.spider_name == spider_name,
                DataStatistics.stat_date >= start_date
            )
        ).order_by(DataStatistics.stat_date.asc()).all()
    
    @staticmethod
    def get_summary_statistics(
        db: Session,
        project_id: Optional[int] = None,
        days: int = 30
    ) -> Dict:
        """获取汇总统计"""
        start_date = datetime.utcnow() - timedelta(days=days)
        
        query = db.query(DataStatistics).filter(DataStatistics.stat_date >= start_date)
        if project_id:
            query = query.filter(DataStatistics.project_id == project_id)
        
        total_records = db.query(func.sum(DataStatistics.total_records)).filter(
            DataStatistics.stat_date >= start_date
        )
        if project_id:
            total_records = total_records.filter(DataStatistics.project_id == project_id)
        
        avg_success_rate = db.query(func.avg(DataStatistics.success_rate)).filter(
            DataStatistics.stat_date >= start_date
        )
        if project_id:
            avg_success_rate = avg_success_rate.filter(DataStatistics.project_id == project_id)
        
        return {
            'total_records': total_records.scalar() or 0,
            'average_success_rate': round(float(avg_success_rate.scalar() or 0), 2),
            'period_days': days
        }


data_quality_service = DataQualityService()
data_statistics_service = DataStatisticsService()
