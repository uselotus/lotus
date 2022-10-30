import React, { FC, useState, useEffect } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import Dashboard from "../components/Dashboard/Dashboard";
import ViewPlans from "../pages/ViewPlans";
import ViewCustomers from "../pages/ViewCustomers";
import SettingsPage from "../pages/settings/SettingsPage";
import StripeRedirect from "../integrations/PaymentProcessorIntegrations";
import SideBar from "../components/SideBar";
import { Avatar, Col, Divider, Layout, PageHeader, Row } from "antd";
import { MenuUnfoldOutlined, MenuFoldOutlined } from "@ant-design/icons";
import CreatePlan from "../pages/CreatePlan";
import ViewMetrics from "../pages/ViewMetrics";
import EditPlan from "../pages/EditPlan";
import ViewExperiments from "../pages/ViewExperiments";
import CreateBacktest from "../pages/CreateBacktest";
import ExperimentResults from "../pages/ExperimentResults";
import PlanDetails from "../components/Plans/PlanDetails/PlanDetails";

const { Header, Sider, Content, Footer } = Layout;

const AppRoutes: FC = () => {
  const [collapse, setCollapse] = useState(false);

  const handleToggle = (event: any) => {
    event.preventDefault();
    collapse ? setCollapse(false) : setCollapse(true);
  };

  useEffect(() => {
    window.innerWidth <= 760 ? setCollapse(true) : setCollapse(false);
  }, []);
  return (
    <div className="bg-darkgold">
      <Layout>
        <Sider
          trigger={null}
          collapsible={false}
          collapsed={collapse}
          style={{ minHeight: "100vh", background: "#FAFAFA" }}
        >
          <SideBar />
        </Sider>

        <Layout style={{ background: "#FAFAFA" }}>
          <Routes>
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/" element={<Dashboard />} />
            <Route path="/plans" element={<ViewPlans />}/>
            <Route path="/plans/:planId" element={<PlanDetails />} />
            <Route path="create-plan" element={<CreatePlan />} />
            <Route
              path="create-version"
              element={<EditPlan type="version" />}
            />
            <Route path="create-custom" element={<EditPlan type="custom" />} />{" "}
            <Route
              path="backtest-plan"
              element={<EditPlan type="backtest" />}
            />
            <Route path="/plan"></Route>
            <Route path="/customers" element={<ViewCustomers />} />
            <Route path="/metrics" element={<ViewMetrics />} />
            <Route path="/customers-create" element={<CreatePlan />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="/redirectstripe" element={<StripeRedirect />} />
            <Route path="/experiments" element={<ViewExperiments />} />
            <Route path="/experiment">
              <Route path=":experimentId" element={<ExperimentResults />} />
            </Route>
            <Route path="create-experiment" element={<CreateBacktest />} />
            {/* <Route path="/experiment">
              <Route path=":experimentId" element={<ExperimentPage />} />
            </Route> */}
            <Route path="*" element={<Navigate to="/dashboard" />} />
          </Routes>
        </Layout>
      </Layout>
    </div>
  );
};

export default AppRoutes;
