import React, { useState } from "react";
import { FeatureType } from "../../types/feature-type";
import { Button, Divider, Modal, Select, Input, message } from "antd";
import { Features } from "../../api/api";
import { UseQueryResult, useQuery } from "react-query";

const { Option } = Select;

const TargetCustomerForm = (props: {
  visible: boolean;
  onCancel: () => void;
  onAddTargetCustomer: (target_customer_id: string) => void;
}) => {
  const [newFeatures, setNewFeatures] = useState<FeatureType[]>([]);
  const [createdFeatureName, setCreatedFeatureName] = useState<string>("");
  const [createdFeatureDescription, setCreatedFeatureDescription] =
    useState<string>("");

  // const {
  //   data: features,
  //   isLoading,
  //   isError,
  // }: UseQueryResult<FeatureType[]> = useQuery<FeatureType[]>(
  //   ["feature_list"],
  //   () =>
  //     Features.getFeatures().then((res) => {
  //       return res;
  //     })
  // );

  return (
    // <Modal
    //   visible={props.visible}
    //   title={"Add Features"}
    //   okText="Add"
    //   okType="default"
    //   okButtonProps={{
    //     className: "bg-black text-white",
    //   }}
    //   onOk={() => {
    //     props.onAddTargetCustomer(newFeatures);
    //   }}
    // >
    //   <div className="grid grid-row-3">
    //     <div className="flex flex-col">
    //       <Select
    //         mode="multiple"
    //         allowClear
    //         placeholder="Select Feature"
    //         value={newFeatures.map((f) => f.feature_name)}
    //         loading={isLoading}
    //         optionLabelProp="label"
    //         onChange={addExistingFeatureToList}
    //         options={features?.map((f) => ({
    //           value: f.feature_name,
    //           label: f.feature_name,
    //         }))}
    //       />
    //     </div>
    //   </div>
    // </Modal>
  );
};

export default TargetCustomerForm;
