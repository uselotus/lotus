/* eslint-disable react/require-default-props */
/* eslint-disable react/no-unused-prop-types */
import React, { PropsWithChildren } from "react";

interface TableProps {
  className?: string;
  grid?: boolean;
}
function Table({ children }: PropsWithChildren<TableProps>) {
  return (
    <div className="px-4 sm:px-6 lg:px-8">
      <div className="mt-8 flex flex-col">
        <div className="-my-2 -mx-4 overflow-x-auto sm:-mx-6 lg:-mx-8">
          <div className="inline-block min-w-full py-2 align-middle md:px-6 lg:px-8">
            <div className="overflow-hidden shadow ring-1 ring-black ring-opacity-5 rounded-sm">
              <table className="min-w-full divide-y divide-gray-300">
                {children}
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function TableHead({
  className,
  grid,
  children,
}: PropsWithChildren<TableProps>) {
  return (
    <thead className={`bg-gray-50 ${className && className}`}>
      <tr className={grid ? "grid grid-rows-1 items-center grid-flow-col" : ""}>
        {children}
      </tr>
    </thead>
  );
}

function TH({ className, children }: PropsWithChildren<TableProps>) {
  return (
    <th
      scope="col"
      className={`py-3 pl-4 pr-3 text-left text-xs font-medium uppercase tracking-wide text-gray-500 sm:pl-6 ${
        className && className
      }`}
    >
      {children}
    </th>
  );
}
function TableBody({
  className,
  grid,
  children,
}: PropsWithChildren<TableProps>) {
  return (
    <tbody
      className={`divide-y divide-gray-200 bg-white ${className && className}`}
    >
      <tr className={grid ? "grid grid-rows-1 items-center grid-flow-col" : ""}>
        {children}
      </tr>
    </tbody>
  );
}
function TD({ className, children }: PropsWithChildren<TableProps>) {
  return (
    <td
      className={`whitespace-nowrap px-3 py-4 text-sm text-gray-500 ${
        className && className
      }`}
    >
      {children}
    </td>
  );
}

Table.Head = TableHead;
Table.Body = TableBody;
Table.TH = TH;
Table.TD = TD;
export default Table;
