# Lysosomal storage disorder (LSD) attention panel

Six genes that **must be reviewed in every run on Uzbek samples**, whatever the main panel of
the run is (project rule recorded 2026-10-12; see [`docs/COHORT_NOTES.md`](../../docs/COHORT_NOTES.md)
for how the pipeline enforces it). Each gene causes a recessive or X-linked lysosomal storage
disorder for which a disease-specific treatment exists, so a missed finding is an actionable miss.

| Gene | Disorder | Inheritance | Ensembl GRCh38 span (gene only) |
|---|---|---|---|
| GBA1 (previous symbol GBA) | Gaucher disease | AR | chr1:155,231,270-155,245,178 |
| GAA | Pompe disease (glycogen storage disease II) | AR | chr17:80,101,526-80,119,881 |
| GLA | Fabry disease | X-linked | chrX:101,393,273-101,408,012 |
| GALC | Krabbe disease (globoid cell leukodystrophy) | AR | chr14:87,837,820-87,993,665 |
| IDUA | Mucopolysaccharidosis type I (Hurler / Scheie) | AR | chr4:986,997-1,008,344 |
| SMPD1 | Acid sphingomyelinase deficiency (Niemann-Pick A/B) | AR | chr11:6,390,381-6,394,998 |

## Files

`lysosomal_storage_genes.txt` -- one gene per line. The first token is the current HGNC symbol;
further tokens on the same line are previous symbols or aliases that stage 07 also matches, so an
annotation from an older snpEff database or ClinVar release that still says `GBA` is not missed.
The BED check in `run_pipeline.sh` and stage 08 use only the first token.

`lysosomal_storage_genes_grch38.bed` -- GRCh38 gene spans with +/-1 kb flanks, sourced from Ensembl
REST `lookup/symbol` (GRCh38, 2026-10-12), same format as the cardiomyopathy BED (0-based start,
gene symbol in column 4). Regenerate for GRCh37 or T2T; do not reuse these coordinates.

## Two ways to use it

1. **As the panel of a run** (`PANEL_GENES` / `PANEL_BED` / `PANEL_NAME="Lysosomal storage"`), when
   the question of the run is these six genes.
2. **As attention genes on top of another panel** (`ATTENTION_GENES=.../lysosomal_storage_genes.txt`),
   which is the Uzbek-sample rule: the main panel stays what the referral asked for, and these six
   genes are reviewed, highlighted and accounted for in every report in addition. With
   `RESTRICT_TO_PANEL=1` the regions must also be in `PANEL_BED` (concatenate the two BEDs), or
   `run_pipeline.sh` refuses to start -- a restricted BED without them would silently never call them.

## Interpretation notes per gene (read before reporting)

These are reasons a call in these genes needs a manual look, not reasons to drop it.

- **GBA1**: the pseudogene GBAP1 lies about 16 kb downstream with ~96 % sequence identity. Short
  reads mis-map between the two, and recombinant alleles (gene/pseudogene fusions) exist. Treat
  any GBA1 call in the 3' exons with low or zero MAPQ reads, odd allele balance, or that matches
  the GBAP1 sequence as a possible mapping artifact until the pileup has been inspected. ClinVar
  and snpEff releases before the HGNC rename annotate the gene as `GBA`.
- **GAA**: pseudodeficiency alleles (c.1726G>A p.Gly576Ser and c.2065G>A p.Glu689Lys, common in
  East and Central Asian populations) lower measured enzyme activity without causing Pompe disease.
  They are not pathogenic and must be labelled as pseudodeficiency when seen, especially in a
  sample that also had a low enzyme assay.
- **GLA**: X-linked. A heterozygous female is not simply a carrier; Fabry disease manifests in
  females. The pipeline passes no sample sex to `bcftools call`, so read the genotype and allele
  depths of chrX calls against the known sex of the sample rather than trusting the het/hom label.
  p.Asp313Tyr (c.937G>T) is a frequent variant of reduced activity whose pathogenicity is disputed.
- **GALC**: the most common Krabbe allele in European populations is a 30 kb deletion. This
  pipeline calls SNVs and small indels only and will never show it; a single heterozygous SNV in
  GALC with a fitting phenotype needs a deletion/CNV assay for the second allele. p.Ile562Thr
  (c.1685T>C, formerly I546T) is a common polymorphism.
- **IDUA**: GC-rich and near the 4p telomere; exome coverage of some exons is often poor, so
  "no variant" needs a coverage check. Pseudodeficiency alleles are described (for example
  p.His82Gln, p.Ala79Thr); p.Trp402Ter and p.Gln70Ter are the common severe alleles.
- **SMPD1**: exon 1 contains a polymorphic hexanucleotide (GCTGGC, Leu-Ala) repeat; in-frame
  indels there are a length polymorphism, not a pathogenic variant. p.Arg610del
  (c.1829_1831del, formerly deltaR608) is the common type B allele.

For all five autosomal recessive genes a single heterozygous variant is a carrier finding unless a
second variant (or a deletion) is found in the same gene; stage 08 scores this when the gene set
carries a mode of inheritance (add `lysosomal` to `TRIAGE_KEYWORDS` so PanelApp supplies it).
