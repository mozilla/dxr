
CREATE INDEX idx_mtname ON members (mtname);
CREATE INDEX idx_mtloc ON members (mtloc);
CREATE INDEX idx_mname ON members (mname);
CREATE INDEX idx_tname ON types (tname);
CREATE INDEX idx_vtype ON stmts (vtype);
CREATE INDEX idx_vmember ON stmts (vmember);
CREATE INDEX idx_tcname ON impl (tcname);
CREATE INDEX idx_tbname ON impl (tbname);
CREATE INDEX idx_members ON members (mshortname);
CREATE INDEX idx_warnings ON warnings (wfile);
