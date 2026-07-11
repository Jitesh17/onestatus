import React from "react";
import { useLang } from "./i18n.js";

// Static in-app documentation. No API calls; safe to render for every role.
// All copy lives in i18n.js so the Docs page follows the site-wide EN/JA toggle.
export default function DocsPage() {
  const { t } = useLang();
  return (
    <>
      <div className="card">
        <h2>{t("docs.overview.title")}</h2>
        <p>{t("docs.overview.p1")}</p>
        <p className="muted">{t("docs.overview.p2")}</p>
      </div>

      <div className="card">
        <h2>{t("docs.pipeline.title")}</h2>
        <ol>
          <li><b>{t("docs.pipeline.step1.label")}</b> {t("docs.pipeline.step1.text")}</li>
          <li><b>{t("docs.pipeline.step2.label")}</b> {t("docs.pipeline.step2.text")}</li>
          <li><b>{t("docs.pipeline.step3.label")}</b> {t("docs.pipeline.step3.text")}</li>
          <li><b>{t("docs.pipeline.step4.label")}</b> {t("docs.pipeline.step4.text")}</li>
          <li><b>{t("docs.pipeline.step5.label")}</b> {t("docs.pipeline.step5.text")}</li>
          <li><b>{t("docs.pipeline.step6.label")}</b> {t("docs.pipeline.step6.text")}</li>
        </ol>
      </div>

      <div className="card">
        <h2>{t("docs.dashboard.title")}</h2>
        <p>{t("docs.dashboard.p1")}</p>
        <p>{t("docs.dashboard.p2")}</p>
        <ul>
          <li><b>{t("docs.dashboard.item1.label")}</b> {t("docs.dashboard.item1.text")}</li>
          <li><b>{t("docs.dashboard.item2.label")}</b> {t("docs.dashboard.item2.text")}</li>
          <li><b>{t("docs.dashboard.item3.label")}</b> {t("docs.dashboard.item3.text")}</li>
        </ul>
      </div>

      <div className="card">
        <h2>{t("docs.arch.title")}</h2>
        <table>
          <thead><tr><th>{t("docs.arch.colPart")}</th><th>{t("docs.arch.colWhat")}</th><th>{t("docs.arch.colWhere")}</th></tr></thead>
          <tbody>
            <tr><td>{t("docs.arch.frontend")}</td><td>{t("docs.arch.frontendWhat")}</td><td>{t("docs.arch.officeServer")}</td></tr>
            <tr><td>{t("docs.arch.backend")}</td><td>{t("docs.arch.backendWhat")}</td><td>{t("docs.arch.officeServer")}</td></tr>
            <tr><td>{t("docs.arch.database")}</td><td>{t("docs.arch.databaseWhat")}</td><td>{t("docs.arch.officeServer")}</td></tr>
            <tr><td>{t("docs.arch.stt")}</td><td>{t("docs.arch.sttWhat")}</td><td>{t("docs.arch.officeServerAlways")}</td></tr>
            <tr><td>{t("docs.arch.llm")}</td><td>{t("docs.arch.llmWhat")}</td><td>{t("docs.arch.llmWhere")}</td></tr>
          </tbody>
        </table>
        <p>{t("docs.arch.p1")}</p>
        <h3>{t("docs.arch.rolesTitle")}</h3>
        <p>{t("docs.arch.rolesP1")}</p>
        <table>
          <thead><tr><th>{t("docs.arch.colRole")}</th><th>{t("docs.arch.colCanDo")}</th></tr></thead>
          <tbody>
            <tr><td>{t("role.member")}</td><td>{t("docs.arch.roleMemberCanDo")}</td></tr>
            <tr><td>{t("role.manager")}</td><td>{t("docs.arch.roleManagerCanDo")}</td></tr>
            <tr><td>{t("role.admin")}</td><td>{t("docs.arch.roleAdminCanDo")}</td></tr>
          </tbody>
        </table>
      </div>

      <div className="card">
        <h2>{t("docs.features.title")}</h2>
        <ul>
          <li>{t("docs.features.item1")}</li>
          <li>{t("docs.features.item2")}</li>
          <li>{t("docs.features.item3")}</li>
          <li>{t("docs.features.item4")}</li>
          <li>{t("docs.features.item5")}</li>
          <li>{t("docs.features.item6")}</li>
          <li>{t("docs.features.item7")}</li>
          <li>{t("docs.features.item8")}</li>
        </ul>
      </div>

      <div className="card">
        <h2>{t("docs.models.title")}</h2>
        <p>{t("docs.models.p1")}</p>
        <table>
          <thead><tr><th>{t("docs.models.colMode")}</th><th>{t("docs.models.colSpeed")}</th><th>{t("docs.models.colData")}</th></tr></thead>
          <tbody>
            <tr><td>{t("docs.models.localCpu")}</td><td>{t("docs.models.localCpuSpeed")}</td><td>{t("docs.models.nothingLeaves")}</td></tr>
            <tr><td>{t("docs.models.localGpu")}</td><td>{t("docs.models.localGpuSpeed")}</td><td>{t("docs.models.nothingLeaves")}</td></tr>
            <tr><td>{t("docs.models.cloudApi")}</td><td>{t("docs.models.cloudApiSpeed")}</td><td>{t("docs.models.cloudDataNote")}</td></tr>
          </tbody>
        </table>
        <h3>{t("docs.models.noGpuTitle")}</h3>
        <p>{t("docs.models.noGpuP1")}</p>
        <ol>
          <li>{t("docs.models.step1")}</li>
          <li>{t("docs.models.step2")}</li>
          <li>{t("docs.models.step3")}</li>
          <li>{t("docs.models.step4")}</li>
        </ol>
        <p className="muted">{t("docs.models.keyNote")}</p>
      </div>
    </>
  );
}
