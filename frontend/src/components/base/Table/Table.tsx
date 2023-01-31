import React, { PropsWithChildren } from "react";
interface TableProps {
  className?: string;
  grid?: boolean;
}
const Table = ({ children, className }: PropsWithChildren<TableProps>) => (
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

const TableHead = ({
  className,
  grid,
  children,
}: PropsWithChildren<TableProps>) => (
  <thead className={`bg-gray-50 ${className && className}`}>
    <tr className={grid ? "grid grid-rows-1 items-center grid-flow-col" : ""}>
      {children}
    </tr>
  </thead>
);

const TH = ({ className, children }: PropsWithChildren<TableProps>) => (
  <th
    scope="col"
    className={`py-3 pl-4 pr-3 text-left text-xs font-medium uppercase tracking-wide text-gray-500 sm:pl-6 ${
      className && className
    }`}
  >
    {children}
  </th>
);
const TableBody = ({
  className,
  grid,
  children,
}: PropsWithChildren<TableProps>) => (
  <tbody
    className={`divide-y divide-gray-200 bg-white ${className && className}`}
  >
    <tr className={grid ? "grid grid-rows-1 items-center grid-flow-col" : ""}>
      {children}
    </tr>
  </tbody>
);
const TD = ({ className, children }: PropsWithChildren<TableProps>) => (
  <td
    className={`whitespace-nowrap px-3 py-4 text-sm text-gray-500 ${
      className && className
    }`}
  >
    {children}
  </td>
);

Table.Head = TableHead;
Table.Body = TableBody;
Table.TH = TH;
Table.TD = TD;
export default Table;
