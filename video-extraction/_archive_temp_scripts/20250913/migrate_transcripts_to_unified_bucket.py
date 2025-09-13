#!/usr/bin/env python3
"""
Migrate transcripts from op-videos-storage to xenodx-video-archive for unified structure

This script:
1. Lists all transcripts in source bucket (op-videos-storage)
2. Copies them to target bucket (xenodx-video-archive) with organized structure
3. Preserves original file formats (.txt, .vtt, .json)
4. Creates mapping for database updates
5. Optionally cleans up source after successful migration

Target structure:
xenodx-video-archive/
├── videos/           # Video files (already exist)
└── transcripts/      # All transcript formats
    ├── txt/          # Plain text transcripts
    ├── vtt/          # VTT subtitle files
    ├── json/         # JSON transcripts with timestamps
    └── archive/      # Legacy/archived transcripts
"""

import boto3
import json
import logging
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
import re
import os

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TranscriptMigrator:
    """Migrate transcripts to unified bucket structure"""
    
    def __init__(self, 
                 source_bucket: str = "op-videos-storage",
                 target_bucket: str = "xenodx-video-archive", 
                 profile: str = "zenex"):
        self.source_bucket = source_bucket
        self.target_bucket = target_bucket
        
        # Initialize S3 client
        session = boto3.Session(profile_name=profile)
        self.s3_client = session.client('s3')
        
        # Migration tracking
        self.migration_plan = {}
        self.migration_results = {
            'successful': 0,
            'failed': 0,
            'skipped': 0,
            'errors': []
        }
    
    def analyze_source_transcripts(self) -> Dict[str, List[Dict]]:
        """Analyze all transcript files in source bucket"""
        logger.info(f"🔍 Analyzing transcripts in {self.source_bucket}...")
        
        try:
            paginator = self.s3_client.get_paginator('list_objects_v2')
            
            transcripts_by_type = defaultdict(list)
            total_size = 0
            total_files = 0
            
            for page in paginator.paginate(Bucket=self.source_bucket, Prefix='transcripts/'):
                if 'Contents' not in page:
                    continue
                    
                for obj in page['Contents']:
                    key = obj['Key']
                    size = obj['Size']
                    last_modified = obj['LastModified']
                    
                    # Skip directories
                    if key.endswith('/'):
                        continue
                    
                    # Categorize by file type and location
                    file_info = {
                        'key': key,
                        'size': size,
                        'size_kb': round(size / 1024, 2),
                        'last_modified': last_modified,
                        'filename': os.path.basename(key)
                    }
                    
                    # Determine file category
                    if '.txt' in key:
                        category = 'txt_files'
                    elif '.vtt' in key:
                        category = 'vtt_files'  
                    elif '.json' in key:
                        category = 'json_files'
                    else:
                        category = 'other_files'
                    
                    # Further categorize by directory
                    if '/archive/' in key:
                        category += '_archived'
                    elif '/classes/' in key:
                        category += '_classes'
                    elif '/other/' in key:
                        category += '_other'
                    elif '/qa/' in key:
                        category += '_qa'
                    elif '/aws/' in key:
                        category += '_aws'
                    
                    transcripts_by_type[category].append(file_info)
                    total_size += size
                    total_files += 1
            
            logger.info(f"✅ Found {total_files} transcript files ({total_size / (1024*1024):.1f} MB total)")
            
            # Print summary by category
            for category, files in transcripts_by_type.items():
                total_cat_size = sum(f['size'] for f in files)
                logger.info(f"   📁 {category}: {len(files)} files ({total_cat_size / 1024:.1f} KB)")
            
            return dict(transcripts_by_type)
            
        except Exception as e:
            logger.error(f"❌ Error analyzing source transcripts: {e}")
            return {}
    
    def create_migration_plan(self, source_transcripts: Dict[str, List[Dict]]) -> Dict:
        """Create migration plan with target paths"""
        logger.info("📋 Creating migration plan...")
        
        migration_plan = {}
        
        for category, files in source_transcripts.items():
            for file_info in files:
                source_key = file_info['key']
                filename = file_info['filename']
                
                # Determine target path based on file type and category
                if '.txt' in source_key:
                    if 'archived' in category:
                        target_key = f"transcripts/archive/{filename}"
                    elif 'classes' in category:
                        target_key = f"transcripts/txt/classes/{filename}"
                    elif 'other' in category:
                        target_key = f"transcripts/txt/other/{filename}"
                    elif 'qa' in category:
                        target_key = f"transcripts/txt/qa/{filename}"
                    else:
                        target_key = f"transcripts/txt/{filename}"
                
                elif '.vtt' in source_key:
                    target_key = f"transcripts/vtt/{filename}"
                
                elif '.json' in source_key:
                    if 'aws' in category:
                        target_key = f"transcripts/json/aws/{filename}"
                    else:
                        target_key = f"transcripts/json/{filename}"
                
                else:
                    target_key = f"transcripts/other/{filename}"
                
                migration_plan[source_key] = {
                    'target_key': target_key,
                    'size': file_info['size'],
                    'size_kb': file_info['size_kb'],
                    'category': category,
                    'filename': filename
                }
        
        logger.info(f"📊 Migration plan created for {len(migration_plan)} files")
        return migration_plan
    
    def check_target_conflicts(self, migration_plan: Dict) -> List[str]:
        """Check for potential conflicts in target bucket"""
        logger.info("🔍 Checking for conflicts in target bucket...")
        
        conflicts = []
        target_keys = [plan['target_key'] for plan in migration_plan.values()]
        
        try:
            # Check existing files in target
            paginator = self.s3_client.get_paginator('list_objects_v2')
            existing_keys = set()
            
            for page in paginator.paginate(Bucket=self.target_bucket, Prefix='transcripts/'):
                if 'Contents' not in page:
                    continue
                for obj in page['Contents']:
                    existing_keys.add(obj['Key'])
            
            # Find conflicts
            for target_key in target_keys:
                if target_key in existing_keys:
                    conflicts.append(target_key)
            
            if conflicts:
                logger.warning(f"⚠️ Found {len(conflicts)} potential conflicts")
                for conflict in conflicts[:10]:  # Show first 10
                    logger.warning(f"   - {conflict}")
                if len(conflicts) > 10:
                    logger.warning(f"   ... and {len(conflicts) - 10} more")
            else:
                logger.info("✅ No conflicts found")
            
            return conflicts
            
        except Exception as e:
            logger.error(f"❌ Error checking conflicts: {e}")
            return []
    
    def estimate_migration_cost(self, migration_plan: Dict) -> Dict:
        """Estimate migration cost and time"""
        total_size = sum(plan['size'] for plan in migration_plan.values())
        total_files = len(migration_plan)
        
        # S3 transfer costs (rough estimates)
        # GET requests: $0.0004 per 1,000 requests
        # PUT requests: $0.005 per 1,000 requests  
        get_cost = (total_files / 1000) * 0.0004
        put_cost = (total_files / 1000) * 0.005
        
        # Data transfer within same region is typically free
        transfer_cost = 0.0
        
        total_cost = get_cost + put_cost + transfer_cost
        
        # Time estimate (rough)
        estimated_seconds = total_files * 0.5  # ~0.5 seconds per file
        estimated_minutes = estimated_seconds / 60
        
        return {
            'total_files': total_files,
            'total_size_mb': round(total_size / (1024 * 1024), 2),
            'estimated_cost_usd': round(total_cost, 4),
            'estimated_time_minutes': round(estimated_minutes, 1),
            'breakdown': {
                'get_requests': total_files,
                'put_requests': total_files,
                'get_cost': round(get_cost, 4),
                'put_cost': round(put_cost, 4)
            }
        }
    
    def migrate_transcripts(self, migration_plan: Dict, dry_run: bool = True) -> Dict:
        """Perform the actual migration"""
        if dry_run:
            logger.info("🔄 DRY RUN - No files will be migrated")
        else:
            logger.info("🚀 Starting transcript migration...")
        
        successful = 0
        failed = 0
        skipped = 0
        errors = []
        
        for i, (source_key, plan) in enumerate(migration_plan.items(), 1):
            target_key = plan['target_key']
            
            if i % 50 == 0:
                logger.info(f"Progress: {i}/{len(migration_plan)} files...")
            
            try:
                if dry_run:
                    logger.debug(f"Would migrate: {source_key} → {target_key}")
                    successful += 1
                else:
                    # Copy file from source to target bucket
                    copy_source = {
                        'Bucket': self.source_bucket,
                        'Key': source_key
                    }
                    
                    self.s3_client.copy_object(
                        CopySource=copy_source,
                        Bucket=self.target_bucket,
                        Key=target_key,
                        MetadataDirective='COPY'
                    )
                    
                    successful += 1
                    logger.debug(f"✅ Migrated: {source_key} → {target_key}")
                    
            except Exception as e:
                failed += 1
                error_msg = f"Failed to migrate {source_key}: {str(e)}"
                errors.append(error_msg)
                logger.error(f"❌ {error_msg}")
        
        results = {
            'successful': successful,
            'failed': failed,
            'skipped': skipped,
            'errors': errors,
            'total_processed': successful + failed + skipped
        }
        
        return results
    
    def save_migration_report(self, analysis: Dict, plan: Dict, estimate: Dict, results: Dict = None) -> str:
        """Save comprehensive migration report"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"transcript_migration_report_{timestamp}.json"
        
        report = {
            'migration_info': {
                'source_bucket': self.source_bucket,
                'target_bucket': self.target_bucket,
                'timestamp': timestamp,
                'generated_at': datetime.now().isoformat()
            },
            'source_analysis': analysis,
            'migration_plan_summary': {
                'total_files': len(plan),
                'file_types': {}
            },
            'cost_estimate': estimate,
            'migration_results': results or {'status': 'plan_only'}
        }
        
        # Add file type breakdown
        for source_key, plan_info in plan.items():
            file_ext = source_key.split('.')[-1] if '.' in source_key else 'unknown'
            if file_ext not in report['migration_plan_summary']['file_types']:
                report['migration_plan_summary']['file_types'][file_ext] = 0
            report['migration_plan_summary']['file_types'][file_ext] += 1
        
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        logger.info(f"💾 Migration report saved: {filename}")
        return filename
    
    def run_migration_analysis(self, dry_run: bool = True):
        """Run complete migration analysis and optionally execute"""
        logger.info("🚀 Starting transcript migration analysis...")
        
        # Step 1: Analyze source transcripts
        source_analysis = self.analyze_source_transcripts()
        if not source_analysis:
            logger.error("❌ Failed to analyze source transcripts")
            return
        
        # Step 2: Create migration plan
        migration_plan = self.create_migration_plan(source_analysis)
        if not migration_plan:
            logger.error("❌ Failed to create migration plan")
            return
        
        # Step 3: Check for conflicts
        conflicts = self.check_target_conflicts(migration_plan)
        
        # Step 4: Estimate costs
        cost_estimate = self.estimate_migration_cost(migration_plan)
        
        # Step 5: Display summary
        logger.info(f"\n{'='*60}")
        logger.info("📊 MIGRATION ANALYSIS SUMMARY")
        logger.info(f"{'='*60}")
        logger.info(f"Source: s3://{self.source_bucket}/transcripts/")
        logger.info(f"Target: s3://{self.target_bucket}/transcripts/")
        logger.info(f"Files to migrate: {cost_estimate['total_files']:,}")
        logger.info(f"Total size: {cost_estimate['total_size_mb']:.1f} MB")
        logger.info(f"Estimated cost: ${cost_estimate['estimated_cost_usd']:.4f}")
        logger.info(f"Estimated time: {cost_estimate['estimated_time_minutes']:.1f} minutes")
        
        if conflicts:
            logger.warning(f"⚠️ Conflicts: {len(conflicts)} files already exist in target")
        
        logger.info(f"{'='*60}")
        
        # Step 6: Execute migration if not dry run
        if dry_run:
            migration_results = self.migrate_transcripts(migration_plan, dry_run=True)
            logger.info("🔍 DRY RUN completed - no files were migrated")
        else:
            logger.info("🚨 EXECUTING MIGRATION...")
            user_confirm = input("Are you sure you want to proceed? (yes/no): ").lower().strip()
            if user_confirm == 'yes':
                migration_results = self.migrate_transcripts(migration_plan, dry_run=False)
                logger.info(f"✅ Migration completed: {migration_results['successful']} successful, {migration_results['failed']} failed")
            else:
                logger.info("Migration cancelled by user")
                migration_results = {'status': 'cancelled_by_user'}
        
        # Step 7: Save report
        report_file = self.save_migration_report(source_analysis, migration_plan, cost_estimate, migration_results)
        
        return {
            'analysis': source_analysis,
            'plan': migration_plan,
            'estimate': cost_estimate,
            'results': migration_results,
            'report_file': report_file
        }


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Migrate transcripts to unified bucket structure')
    parser.add_argument('--execute', action='store_true', help='Execute migration (default is dry run)')
    parser.add_argument('--source-bucket', default='op-videos-storage', help='Source bucket name')
    parser.add_argument('--target-bucket', default='xenodx-video-archive', help='Target bucket name')
    parser.add_argument('--profile', default='zenex', help='AWS profile to use')
    
    args = parser.parse_args()
    
    # Create migrator and run analysis
    migrator = TranscriptMigrator(args.source_bucket, args.target_bucket, args.profile)
    results = migrator.run_migration_analysis(dry_run=not args.execute)
    
    if results:
        print(f"\n💡 Next steps:")
        print(f"   • Review migration report: {results['report_file']}")
        if args.execute:
            print(f"   • Migration completed!")
        else:
            print(f"   • Run with --execute to perform migration")
            print(f"   • Command: python3 {__file__} --execute")


if __name__ == "__main__":
    main()