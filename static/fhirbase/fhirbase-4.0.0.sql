CREATE EXTENSION IF NOT EXISTS pgcrypto;
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'resource_status') THEN
       CREATE TYPE resource_status AS ENUM ('created', 'updated', 'deleted', 'recreated');
    END IF;
END
$$;
CREATE TABLE IF NOT EXISTS transaction (
  id serial primary key,
  ts timestamptz DEFAULT current_timestamp,
  resource jsonb);
CREATE TABLE IF NOT EXISTS "devicerequest" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'DeviceRequest',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "devicerequest_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'DeviceRequest',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "servicerequest" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'ServiceRequest',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "servicerequest_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'ServiceRequest',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "devicemetric" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'DeviceMetric',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "devicemetric_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'DeviceMetric',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "careplan" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'CarePlan',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "careplan_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'CarePlan',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "observation" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Observation',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "observation_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Observation',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "enrollmentrequest" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'EnrollmentRequest',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "enrollmentrequest_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'EnrollmentRequest',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "group" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Group',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "group_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Group',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "messagedefinition" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'MessageDefinition',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "messagedefinition_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'MessageDefinition',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "appointment" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Appointment',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "appointment_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Appointment',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "biologicallyderivedproduct" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'BiologicallyDerivedProduct',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "biologicallyderivedproduct_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'BiologicallyDerivedProduct',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "questionnaireresponse" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'QuestionnaireResponse',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "questionnaireresponse_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'QuestionnaireResponse',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "effectevidencesynthesis" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'EffectEvidenceSynthesis',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "effectevidencesynthesis_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'EffectEvidenceSynthesis',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "medicinalproductcontraindication" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'MedicinalProductContraindication',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "medicinalproductcontraindication_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'MedicinalProductContraindication',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "episodeofcare" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'EpisodeOfCare',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "episodeofcare_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'EpisodeOfCare',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "evidence" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Evidence',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "evidence_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Evidence',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "substancepolymer" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'SubstancePolymer',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "substancepolymer_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'SubstancePolymer',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "supplydelivery" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'SupplyDelivery',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "supplydelivery_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'SupplyDelivery',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "substancenucleicacid" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'SubstanceNucleicAcid',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "substancenucleicacid_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'SubstanceNucleicAcid',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "adverseevent" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'AdverseEvent',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "adverseevent_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'AdverseEvent',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "endpoint" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Endpoint',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "endpoint_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Endpoint',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "substancereferenceinformation" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'SubstanceReferenceInformation',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "substancereferenceinformation_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'SubstanceReferenceInformation',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "substancesourcematerial" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'SubstanceSourceMaterial',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "substancesourcematerial_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'SubstanceSourceMaterial',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "compartmentdefinition" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'CompartmentDefinition',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "compartmentdefinition_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'CompartmentDefinition',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "detectedissue" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'DetectedIssue',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "detectedissue_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'DetectedIssue',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "medicationadministration" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'MedicationAdministration',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "medicationadministration_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'MedicationAdministration',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "evidencevariable" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'EvidenceVariable',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "evidencevariable_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'EvidenceVariable',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "implementationguide" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'ImplementationGuide',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "implementationguide_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'ImplementationGuide',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "goal" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Goal',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "goal_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Goal',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "communication" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Communication',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "communication_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Communication',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "schedule" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Schedule',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "schedule_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Schedule',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "documentreference" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'DocumentReference',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "documentreference_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'DocumentReference',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "organizationaffiliation" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'OrganizationAffiliation',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "organizationaffiliation_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'OrganizationAffiliation',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "devicedefinition" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'DeviceDefinition',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "devicedefinition_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'DeviceDefinition',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "coverage" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Coverage',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "coverage_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Coverage',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "auditevent" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'AuditEvent',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "auditevent_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'AuditEvent',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "messageheader" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'MessageHeader',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "messageheader_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'MessageHeader',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "contract" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Contract',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "contract_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Contract',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "testreport" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'TestReport',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "testreport_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'TestReport',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "codesystem" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'CodeSystem',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "codesystem_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'CodeSystem',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "plandefinition" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'PlanDefinition',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "plandefinition_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'PlanDefinition',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "invoice" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Invoice',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "invoice_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Invoice',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "claimresponse" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'ClaimResponse',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "claimresponse_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'ClaimResponse',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "chargeitem" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'ChargeItem',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "chargeitem_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'ChargeItem',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "coverageeligibilityresponse" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'CoverageEligibilityResponse',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "coverageeligibilityresponse_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'CoverageEligibilityResponse',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "bodystructure" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'BodyStructure',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "bodystructure_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'BodyStructure',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "parameters" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Parameters',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "parameters_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Parameters',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "clinicalimpression" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'ClinicalImpression',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "clinicalimpression_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'ClinicalImpression',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "familymemberhistory" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'FamilyMemberHistory',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "familymemberhistory_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'FamilyMemberHistory',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "medicinalproductauthorization" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'MedicinalProductAuthorization',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "medicinalproductauthorization_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'MedicinalProductAuthorization',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "binary" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Binary',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "binary_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Binary',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "composition" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Composition',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "composition_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Composition',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "practitionerrole" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'PractitionerRole',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "practitionerrole_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'PractitionerRole',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "healthcareservice" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'HealthcareService',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "healthcareservice_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'HealthcareService',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "patient" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Patient',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "patient_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Patient',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "medicationdispense" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'MedicationDispense',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "medicationdispense_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'MedicationDispense',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "deviceusestatement" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'DeviceUseStatement',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "deviceusestatement_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'DeviceUseStatement',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "structuremap" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'StructureMap',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "structuremap_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'StructureMap',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "immunizationevaluation" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'ImmunizationEvaluation',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "immunizationevaluation_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'ImmunizationEvaluation',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "library" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Library',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "library_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Library',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "basic" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Basic',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "basic_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Basic',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "slot" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Slot',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "slot_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Slot',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "activitydefinition" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'ActivityDefinition',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "activitydefinition_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'ActivityDefinition',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "medicinalproductinteraction" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'MedicinalProductInteraction',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "medicinalproductinteraction_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'MedicinalProductInteraction',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "molecularsequence" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'MolecularSequence',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "molecularsequence_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'MolecularSequence',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "specimen" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Specimen',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "specimen_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Specimen',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "diagnosticreport" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'DiagnosticReport',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "diagnosticreport_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'DiagnosticReport',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "subscription" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Subscription',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "subscription_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Subscription',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "requestgroup" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'RequestGroup',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "requestgroup_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'RequestGroup',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "provenance" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Provenance',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "provenance_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Provenance',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "medicinalproduct" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'MedicinalProduct',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "medicinalproduct_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'MedicinalProduct',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "chargeitemdefinition" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'ChargeItemDefinition',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "chargeitemdefinition_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'ChargeItemDefinition',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "practitioner" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Practitioner',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "practitioner_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Practitioner',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "medicinalproductpackaged" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'MedicinalProductPackaged',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "medicinalproductpackaged_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'MedicinalProductPackaged',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "flag" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Flag',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "flag_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Flag',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "explanationofbenefit" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'ExplanationOfBenefit',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "explanationofbenefit_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'ExplanationOfBenefit',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "linkage" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Linkage',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "linkage_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Linkage',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "operationoutcome" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'OperationOutcome',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "operationoutcome_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'OperationOutcome',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "medicinalproductpharmaceutical" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'MedicinalProductPharmaceutical',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "medicinalproductpharmaceutical_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'MedicinalProductPharmaceutical',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "immunization" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Immunization',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "immunization_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Immunization',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "medicationknowledge" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'MedicationKnowledge',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "medicationknowledge_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'MedicationKnowledge',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "researchsubject" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'ResearchSubject',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "researchsubject_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'ResearchSubject',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "medicinalproductindication" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'MedicinalProductIndication',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "medicinalproductindication_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'MedicinalProductIndication',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "paymentnotice" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'PaymentNotice',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "paymentnotice_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'PaymentNotice',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "namingsystem" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'NamingSystem',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "namingsystem_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'NamingSystem',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "medicationstatement" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'MedicationStatement',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "medicationstatement_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'MedicationStatement',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "enrollmentresponse" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'EnrollmentResponse',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "enrollmentresponse_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'EnrollmentResponse',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "nutritionorder" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'NutritionOrder',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "nutritionorder_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'NutritionOrder',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "questionnaire" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Questionnaire',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "questionnaire_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Questionnaire',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "account" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Account',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "account_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Account',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "eventdefinition" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'EventDefinition',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "eventdefinition_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'EventDefinition',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "medicinalproductundesirableeffect" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'MedicinalProductUndesirableEffect',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "medicinalproductundesirableeffect_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'MedicinalProductUndesirableEffect',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "substancespecification" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'SubstanceSpecification',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "substancespecification_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'SubstanceSpecification',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "communicationrequest" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'CommunicationRequest',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "communicationrequest_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'CommunicationRequest',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "specimendefinition" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'SpecimenDefinition',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "specimendefinition_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'SpecimenDefinition',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "verificationresult" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'VerificationResult',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "verificationresult_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'VerificationResult',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "documentmanifest" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'DocumentManifest',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "documentmanifest_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'DocumentManifest',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "task" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Task',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "task_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Task',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "riskevidencesynthesis" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'RiskEvidenceSynthesis',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "riskevidencesynthesis_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'RiskEvidenceSynthesis',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "valueset" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'ValueSet',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "valueset_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'ValueSet',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "claim" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Claim',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "claim_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Claim',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "insuranceplan" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'InsurancePlan',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "insuranceplan_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'InsurancePlan',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "examplescenario" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'ExampleScenario',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "examplescenario_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'ExampleScenario',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "researchstudy" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'ResearchStudy',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "researchstudy_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'ResearchStudy',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "medicationrequest" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'MedicationRequest',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "medicationrequest_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'MedicationRequest',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "measure" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Measure',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "measure_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Measure',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "list" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'List',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "list_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'List',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "encounter" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Encounter',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "encounter_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Encounter',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "capabilitystatement" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'CapabilityStatement',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "capabilitystatement_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'CapabilityStatement',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "visionprescription" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'VisionPrescription',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "visionprescription_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'VisionPrescription',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "riskassessment" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'RiskAssessment',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "riskassessment_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'RiskAssessment',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "substanceprotein" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'SubstanceProtein',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "substanceprotein_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'SubstanceProtein',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "immunizationrecommendation" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'ImmunizationRecommendation',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "immunizationrecommendation_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'ImmunizationRecommendation',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "relatedperson" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'RelatedPerson',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "relatedperson_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'RelatedPerson',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "medication" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Medication',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "medication_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Medication',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "appointmentresponse" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'AppointmentResponse',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "appointmentresponse_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'AppointmentResponse',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "researchelementdefinition" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'ResearchElementDefinition',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "researchelementdefinition_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'ResearchElementDefinition',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "substance" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Substance',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "substance_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Substance',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "paymentreconciliation" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'PaymentReconciliation',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "paymentreconciliation_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'PaymentReconciliation',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "conceptmap" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'ConceptMap',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "conceptmap_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'ConceptMap',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "person" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Person',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "person_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Person',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "condition" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Condition',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "condition_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Condition',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "careteam" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'CareTeam',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "careteam_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'CareTeam',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "catalogentry" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'CatalogEntry',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "catalogentry_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'CatalogEntry',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "structuredefinition" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'StructureDefinition',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "structuredefinition_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'StructureDefinition',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "procedure" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Procedure',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "procedure_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Procedure',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "consent" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Consent',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "consent_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Consent',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "observationdefinition" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'ObservationDefinition',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "observationdefinition_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'ObservationDefinition',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "attribute" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Attribute',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "attribute_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Attribute',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "location" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Location',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "location_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Location',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "organization" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Organization',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "organization_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Organization',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "device" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Device',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "device_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Device',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "supplyrequest" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'SupplyRequest',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "supplyrequest_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'SupplyRequest',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "allergyintolerance" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'AllergyIntolerance',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "allergyintolerance_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'AllergyIntolerance',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "researchdefinition" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'ResearchDefinition',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "researchdefinition_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'ResearchDefinition',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "operationdefinition" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'OperationDefinition',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "operationdefinition_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'OperationDefinition',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "medicinalproductmanufactured" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'MedicinalProductManufactured',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "medicinalproductmanufactured_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'MedicinalProductManufactured',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "imagingstudy" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'ImagingStudy',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "imagingstudy_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'ImagingStudy',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "coverageeligibilityrequest" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'CoverageEligibilityRequest',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "coverageeligibilityrequest_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'CoverageEligibilityRequest',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "medicinalproductingredient" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'MedicinalProductIngredient',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "medicinalproductingredient_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'MedicinalProductIngredient',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "guidanceresponse" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'GuidanceResponse',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "guidanceresponse_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'GuidanceResponse',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "media" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Media',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "media_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'Media',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "measurereport" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'MeasureReport',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "measurereport_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'MeasureReport',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "graphdefinition" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'GraphDefinition',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "graphdefinition_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'GraphDefinition',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "terminologycapabilities" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'TerminologyCapabilities',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "terminologycapabilities_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'TerminologyCapabilities',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE TABLE IF NOT EXISTS "metadataresource" (
  id text primary key,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'MetadataResource',
  status resource_status not null,
  resource jsonb not null
);
CREATE TABLE IF NOT EXISTS "metadataresource_history" (
  id text,
  txid bigint not null,
  ts timestamptz DEFAULT current_timestamp,
  resource_type text default 'MetadataResource',
  status resource_status not null,
  resource jsonb not null,
  PRIMARY KEY (id, txid)
);
CREATE OR REPLACE FUNCTION fhirbase_genid()
RETURNS text AS $$
  select gen_random_uuid()::text
$$ LANGUAGE sql;


CREATE TYPE _resource AS (
  id text,
  txid bigint,
  ts timestamptz,
  resource_type text,
  status resource_status,
  resource jsonb
);


CREATE OR REPLACE FUNCTION _fhirbase_to_resource(x _resource)
RETURNS jsonb AS $$
 select x.resource || jsonb_build_object(
  'resourceType', x.resource_type,
  'id', x.id,
  'meta', coalesce(x.resource->'meta', '{}'::jsonb) || jsonb_build_object(
    'lastUpdated', x.ts,
    'versionId', x.txid::text
  )
 );
$$ LANGUAGE sql;


CREATE OR REPLACE FUNCTION fhirbase_create(resource jsonb, txid bigint)
RETURNS jsonb AS $FUNCTION$
DECLARE
  _sql text;
  rt text;
  rid text;
  result jsonb;
BEGIN
    rt   := resource->>'resourceType';
    rid  := coalesce(resource->>'id', fhirbase_genid());
    _sql := format($SQL$
      WITH archived AS (
        INSERT INTO %s (id, txid, ts, status, resource)
        SELECT id, txid, ts, status, resource
        FROM %s
        WHERE id = $2
        RETURNING *
      ), inserted AS (
         INSERT INTO %s (id, ts, txid, status, resource)
         VALUES ($2, current_timestamp, $1, 'created', $3)
         ON CONFLICT (id)
         DO UPDATE SET
          txid = $1,
          ts = current_timestamp,
          status = 'recreated',
          resource = $3
         RETURNING *
      )

      select _fhirbase_to_resource(i.*) from inserted i

      $SQL$,
      rt || '_history', rt, rt, rt);

  EXECUTE _sql
  USING txid, rid, jsonb_set(resource, '{id}', to_jsonb(rid::text), true)
  INTO result;

  return result;

END
$FUNCTION$ LANGUAGE plpgsql;


CREATE OR REPLACE FUNCTION fhirbase_create(resource jsonb)
RETURNS jsonb AS $FUNCTION$
   SELECT fhirbase_create(resource, nextval('transaction_id_seq'));
$FUNCTION$ LANGUAGE sql;


CREATE OR REPLACE FUNCTION fhirbase_update(resource jsonb, txid bigint)
RETURNS jsonb AS $FUNCTION$
DECLARE
  _sql text ;
  rt text;
  rid text;
  result jsonb;
BEGIN
    rt   := resource->>'resourceType';
    rid  := resource->>'id';

    CASE WHEN (rid IS NULL) THEN
      RAISE EXCEPTION 'Resource does not have and id' USING HINT = 'Resource does not have and id';
    ELSE
    END CASE;

    _sql := format($SQL$
      WITH archived AS (
        INSERT INTO %s (id, txid, ts, status, resource)
        SELECT id, txid, ts, status, resource
        FROM %s
        WHERE id = $2
        RETURNING *
      ), inserted AS (
         INSERT INTO %s (id, ts, txid, status, resource)
         VALUES ($2, current_timestamp, $1, 'created', $3)
         ON CONFLICT (id)
         DO UPDATE SET
          txid = $1,
          ts = current_timestamp,
          status = 'updated',
          resource = $3
         RETURNING *
      )

      select _fhirbase_to_resource(i.*) from inserted i

      $SQL$,
      rt || '_history', rt, rt, rt);

  EXECUTE _sql
  USING txid, rid, (resource - 'id')
  INTO result;

  return result;

END
$FUNCTION$ LANGUAGE plpgsql;


CREATE OR REPLACE FUNCTION fhirbase_update(resource jsonb)
RETURNS jsonb AS $FUNCTION$
   SELECT fhirbase_update(resource, nextval('transaction_id_seq'));
$FUNCTION$ LANGUAGE sql;


CREATE OR REPLACE FUNCTION fhirbase_read(resource_type text, id text)
RETURNS jsonb AS $FUNCTION$
DECLARE
  _sql text;
  result jsonb;
BEGIN
  _sql := format($SQL$
    SELECT _fhirbase_to_resource(row(r.*)::_resource) FROM %s r WHERE r.id = $1
  $SQL$,
  resource_type
  );

  EXECUTE _sql USING id INTO result;

  return result;
END
$FUNCTION$ LANGUAGE plpgsql;


CREATE OR REPLACE FUNCTION fhirbase_delete(resource_type text, id text, txid bigint)
RETURNS jsonb AS $FUNCTION$
DECLARE
  _sql text;
  rt text;
  rid text;
  result jsonb;
BEGIN
    rt   := resource_type;
    rid  := id;
    _sql := format($SQL$
      WITH archived AS (
        INSERT INTO %s (id, txid, ts, status, resource)
        SELECT id, txid, ts, status, resource
        FROM %s WHERE id = $2
        RETURNING *
      ), deleted AS (
         INSERT INTO %s (id, txid, ts, status, resource)
         SELECT id, $1, current_timestamp, status, resource
         FROM %s WHERE id = $2
         RETURNING *
      ), dropped AS (
         DELETE FROM %s WHERE id = $2 RETURNING *
      )
      select _fhirbase_to_resource(i.*) from archived i

      $SQL$,
      rt || '_history', rt, rt || '_history', rt, rt);

  EXECUTE _sql
  USING txid, rid
  INTO result;

  return result;

END
$FUNCTION$ LANGUAGE plpgsql;


CREATE OR REPLACE FUNCTION fhirbase_delete(resource_type text, id text)
RETURNS jsonb AS $FUNCTION$
   SELECT fhirbase_delete(resource_type, id, nextval('transaction_id_seq'));
$FUNCTION$ LANGUAGE sql;

CREATE TABLE IF NOT EXISTS "concept" (
    id text primary key,
    txid bigint not null,
    ts timestamptz DEFAULT current_timestamp,
    resource_type text default 'Concept',
    status resource_status not null,
    resource jsonb not null
);

CREATE TABLE IF NOT EXISTS "concept_history" (
    id text,
    txid bigint not null,
    ts timestamptz DEFAULT current_timestamp,
    resource_type text default 'Concept',
    status resource_status not null,
    resource jsonb not null,
    PRIMARY KEY (id, txid)
);

